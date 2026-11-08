import { useCallback, useEffect, useRef, useState } from 'react'
import { createSession, removeDocument, uploadDocument } from '../api/client'
import { StreamAbortError, streamChat } from '../api/stream'
import { E2E_MODE, MOCK_MODE } from '../config'
import { resetMockSessionState } from '../mocks/mockSession'
import { useChatStore } from '../state/chatStore'
import type { ChatRequest, SseEvent } from '../types/contracts'

const GENERIC_ERROR = 'Sorry, something went wrong on our side. Please try again.'
const RATE_LIMIT_MESSAGE = "You're sending messages a little fast. Give it a moment and try again."
const SESSION_EXPIRED_MESSAGE = 'This chat has expired. Start a new inquiry to continue.'
const QUIET_TYPING_DELAY_MS = 400

function friendlyStreamError(code: string, message: string): { code: string; message: string } {
  if (code === 'rate_limited') return { code, message: RATE_LIMIT_MESSAGE }
  if (code === 'session_not_found') return { code, message: SESSION_EXPIRED_MESSAGE }
  return { code: code || 'stream_failed', message: message || GENERIC_ERROR }
}

/** Draft keys an edit of `key` writes (`contact_number` is saved as mobile or landline). */
function savedKeys(key: string): string[] {
  return key === 'contact_number' ? ['mobile', 'landline'] : [key]
}

function actionQueueKey(action: string, payload: Record<string, unknown>): string {
  return `${action}:${JSON.stringify(payload)}`
}

export function useChatSession() {
  const { state, dispatch, initialSession } = useChatStore()
  const abortRef = useRef<AbortController | null>(null)
  const actionQueueRef = useRef<ChatRequest[]>([])
  const queuedKeysRef = useRef<Set<string>>(new Set())
  const [queuedActions, setQueuedActions] = useState<Set<string>>(() => new Set())
  const [actionTypingDelay, setActionTypingDelay] = useState(false)

  const syncQueuedUi = useCallback(() => {
    setQueuedActions(new Set(queuedKeysRef.current))
  }, [])

  const runStream = useCallback(
    async (body: ChatRequest) => {
      if (!state.sessionId || state.status === 'streaming') return

      dispatch({ type: 'turnStarted' })

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        let streamError = { code: 'agent_error', message: GENERIC_ERROR }
        const outcome = await streamChat(
          state.sessionId,
          body,
          (event) => {
            dispatch({ type: 'sse', event })
            if (event.event === 'error') {
              streamError = {
                code: String(event.data.code ?? 'agent_error'),
                message: String(event.data.message ?? GENERIC_ERROR),
              }
            }
          },
          controller.signal,
        )
        if (outcome === 'error') {
          dispatch({
            type: 'streamFailed',
            error: friendlyStreamError(streamError.code, streamError.message),
            pendingRetry: body,
          })
        }
      } catch (err) {
        if (
          err instanceof StreamAbortError ||
          (err instanceof DOMException && err.name === 'AbortError')
        ) {
          return
        }
        const code =
          err && typeof err === 'object' && 'code' in err
            ? String((err as { code: string }).code)
            : 'stream_failed'
        const message = err instanceof Error ? err.message : GENERIC_ERROR
        dispatch({
          type: 'streamFailed',
          error: friendlyStreamError(code, message),
          pendingRetry: body,
        })
      }
    },
    [dispatch, state.sessionId, state.status],
  )

  const flushActionQueue = useCallback(() => {
    if (state.status !== 'idle' || !state.sessionId) return
    while (actionQueueRef.current.length > 0) {
      const next = actionQueueRef.current[0]
      if (next.type !== 'action') {
        actionQueueRef.current.shift()
        continue
      }
      const key = actionQueueKey(next.action, next.payload)
      actionQueueRef.current.shift()
      queuedKeysRef.current.delete(key)
      syncQueuedUi()
      setActionTypingDelay(true)
      void runStream(next)
      return
    }
  }, [runStream, state.sessionId, state.status, syncQueuedUi])

  // Also on queue changes: an action queued while idle (documents_updated after an upload)
  // goes out straight away instead of waiting for the next turn.
  useEffect(() => {
    flushActionQueue()
  }, [flushActionQueue, queuedActions, state.status])

  useEffect(() => {
    if (state.status !== 'error') return
    actionQueueRef.current = []
    queuedKeysRef.current.clear()
    syncQueuedUi()
  }, [state.status, syncQueuedUi])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const session = initialSession ?? (await createSession())
        if (cancelled) return
        dispatch({
          type: 'sessionCreated',
          sessionId: session.session_id,
          messages: session.messages,
          cards: session.cards,
          draft: session.draft,
        })
        if (E2E_MODE && typeof window !== 'undefined') {
          const w = window as Window & { __e2eSessionId?: string }
          w.__e2eSessionId = session.session_id
        }
      } catch {
        if (cancelled) return
        dispatch({
          type: 'streamFailed',
          error: { code: 'session_failed', message: GENERIC_ERROR },
          pendingRetry: null,
        })
      }
    })()

    return () => {
      cancelled = true
      abortRef.current?.abort()
    }
  }, [dispatch, initialSession])

  useEffect(
    () => () => {
      abortRef.current?.abort()
    },
    [],
  )

  useEffect(() => {
    if (state.status !== 'streaming') {
      setActionTypingDelay(false)
    }
  }, [state.status])

  useEffect(() => {
    if (!actionTypingDelay || state.status !== 'streaming') return
    const timer = window.setTimeout(() => {
      setActionTypingDelay(false)
    }, QUIET_TYPING_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [actionTypingDelay, state.status])

  useEffect(() => {
    if (!state.awaitingReply) {
      setActionTypingDelay(false)
    }
  }, [state.awaitingReply])

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || state.status === 'streaming') return
      setActionTypingDelay(false)
      dispatch({ type: 'userMessage', text: trimmed })
      void runStream({ type: 'message', text: trimmed })
    },
    [dispatch, runStream, state.status],
  )

  const enqueueAction = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      const key = actionQueueKey(action, payload)
      if (queuedKeysRef.current.has(key)) return
      queuedKeysRef.current.add(key)
      actionQueueRef.current.push({ type: 'action', action, payload })
      syncQueuedUi()
    },
    [syncQueuedUi],
  )

  const sendAction = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      if (state.status === 'streaming') {
        enqueueAction(action, payload)
        return
      }
      setActionTypingDelay(true)
      void runStream({ type: 'action', action, payload })
    },
    [enqueueAction, runStream, state.status],
  )

  const isActionQueued = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      return queuedActions.has(actionQueueKey(action, payload))
    },
    [queuedActions],
  )

  const editReviewField = useCallback(
    async (key: string, value: string) => {
      if (!state.sessionId || state.status === 'streaming') return false

      dispatch({ type: 'turnStarted' })
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      let saved = false
      try {
        const outcome = await streamChat(
          state.sessionId,
          { type: 'action', action: 'edit_field', payload: { key, value } },
          (event: SseEvent) => {
            dispatch({ type: 'sse', event })
            if (
              event.event === 'draft' &&
              Array.isArray(event.data.changed_keys) &&
              savedKeys(key).some((k) => event.data.changed_keys.includes(k))
            ) {
              saved = true
            }
          },
          controller.signal,
        )
        if (outcome === 'error') return false
        return saved
      } catch {
        return false
      }
    },
    [dispatch, state.sessionId, state.status],
  )

  // documents_updated goes through the action queue: an upload can finish while the agent is
  // still replying (the documents card arrives mid-turn), and runStream drops a call made
  // while streaming.
  const maybeNotifyDocumentsComplete = useCallback(
    (beforeUploaded: number, beforeTotal: number, afterUploaded: number, afterTotal: number) => {
      if (beforeUploaded < beforeTotal && afterUploaded >= afterTotal) {
        enqueueAction('documents_updated', {})
      }
    },
    [enqueueAction],
  )

  const uploadDocumentForType = useCallback(
    async (docType: string, file: File) => {
      if (!state.sessionId) return
      const beforeUploaded = state.draft?.checks.required_docs_uploaded ?? 0
      const beforeTotal = state.draft?.checks.required_docs_total ?? 2
      const result = await uploadDocument(state.sessionId, docType, file)
      dispatch({ type: 'sse', event: { event: 'ui_card', data: result.card } })
      dispatch({ type: 'sse', event: { event: 'draft', data: result.draft } })
      // A profile that filled fields or disagrees with one gets an agent turn of its own
      // (demo feedback §3.7), even when other documents are still missing.
      if ((result.fields_filled?.length ?? 0) > 0 || (result.mismatches?.length ?? 0) > 0) {
        // The note's status line covers "all documents in" too, so no second call.
        enqueueAction('documents_updated', { doc_type: docType })
        return
      }
      maybeNotifyDocumentsComplete(
        beforeUploaded,
        beforeTotal,
        result.draft.checks.required_docs_uploaded,
        result.draft.checks.required_docs_total,
      )
    },
    [dispatch, enqueueAction, maybeNotifyDocumentsComplete, state.draft?.checks, state.sessionId],
  )

  const removeDocumentForType = useCallback(
    async (docType: string) => {
      if (!state.sessionId) return
      const beforeUploaded = state.draft?.checks.required_docs_uploaded ?? 0
      const beforeTotal = state.draft?.checks.required_docs_total ?? 2
      const result = await removeDocument(state.sessionId, docType)
      dispatch({ type: 'sse', event: { event: 'ui_card', data: result.card } })
      dispatch({ type: 'sse', event: { event: 'draft', data: result.draft } })
      maybeNotifyDocumentsComplete(
        beforeUploaded,
        beforeTotal,
        result.draft.checks.required_docs_uploaded,
        result.draft.checks.required_docs_total,
      )
    },
    [dispatch, maybeNotifyDocumentsComplete, state.draft?.checks, state.sessionId],
  )

  const setDocumentNumber = useCallback(
    (key: string, value: string) => {
      sendAction('set_document_number', { key, value })
    },
    [sendAction],
  )

  const retry = useCallback(() => {
    if (!state.pendingRetry) return
    void runStream(state.pendingRetry)
  }, [runStream, state.pendingRetry])

  const restart = useCallback(async () => {
    abortRef.current?.abort()
    actionQueueRef.current = []
    queuedKeysRef.current.clear()
    syncQueuedUi()
    if (MOCK_MODE) resetMockSessionState()
    dispatch({ type: 'reset' })
    try {
      const session = await createSession()
      dispatch({
        type: 'sessionCreated',
        sessionId: session.session_id,
        messages: session.messages,
        cards: session.cards,
        draft: session.draft,
      })
    } catch {
      dispatch({
        type: 'streamFailed',
        error: { code: 'session_failed', message: GENERIC_ERROR },
        pendingRetry: null,
      })
    }
  }, [dispatch, syncQueuedUi])

  const showTyping = state.status === 'streaming' && state.awaitingReply && !actionTypingDelay

  return {
    ...state,
    sendMessage,
    sendAction,
    isActionQueued,
    editReviewField,
    uploadDocument: uploadDocumentForType,
    removeDocument: removeDocumentForType,
    setDocumentNumber,
    retry,
    restart,
    isStreaming: state.status === 'streaming',
    showTyping,
  }
}
