import { useCallback, useEffect, useRef } from 'react'
import { createSession, removeDocument, uploadDocument } from '../api/client'
import { StreamAbortError, streamChat } from '../api/stream'
import { MOCK_MODE } from '../config'
import { resetMockSessionState } from '../mocks/mockSession'
import { useChatStore } from '../state/chatStore'
import type { ChatRequest, SseEvent } from '../types/contracts'

const GENERIC_ERROR = 'Sorry, something went wrong on our side. Please try again.'
const RATE_LIMIT_MESSAGE = "You're sending messages a little fast. Give it a moment and try again."
const SESSION_EXPIRED_MESSAGE = 'This chat has expired. Start a new inquiry to continue.'

function friendlyStreamError(code: string, message: string): { code: string; message: string } {
  if (code === 'rate_limited') return { code, message: RATE_LIMIT_MESSAGE }
  if (code === 'session_not_found') return { code, message: SESSION_EXPIRED_MESSAGE }
  return { code: code || 'stream_failed', message: message || GENERIC_ERROR }
}

export function useChatSession() {
  const { state, dispatch } = useChatStore()
  const abortRef = useRef<AbortController | null>(null)

  const runStream = useCallback(
    async (body: ChatRequest) => {
      if (!state.sessionId || state.status === 'streaming') return

      dispatch({ type: 'turnStarted' })

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        let streamError = { code: 'agent_error', message: GENERIC_ERROR }
        const outcome = await streamChat(state.sessionId, body, (event) => {
          dispatch({ type: 'sse', event })
          if (event.event === 'error') {
            streamError = {
              code: String(event.data.code ?? 'agent_error'),
              message: String(event.data.message ?? GENERIC_ERROR),
            }
          }
        }, controller.signal)
        if (outcome === 'error') {
          dispatch({
            type: 'streamFailed',
            error: friendlyStreamError(streamError.code, streamError.message),
            pendingRetry: body,
          })
        }
      } catch (err) {
        if (err instanceof StreamAbortError || (err instanceof DOMException && err.name === 'AbortError')) {
          return
        }
        const code =
          err && typeof err === 'object' && 'code' in err ? String((err as { code: string }).code) : 'stream_failed'
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

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const session = await createSession()
        if (cancelled) return
        dispatch({
          type: 'sessionCreated',
          sessionId: session.session_id,
          messages: session.messages,
          cards: session.cards,
          draft: session.draft,
        })
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
  }, [dispatch])

  useEffect(
    () => () => {
      abortRef.current?.abort()
    },
    [],
  )

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || state.status === 'streaming') return
      dispatch({ type: 'userMessage', text: trimmed })
      void runStream({ type: 'message', text: trimmed })
    },
    [dispatch, runStream, state.status],
  )

  const sendAction = useCallback(
    (action: string, payload: Record<string, unknown>) => {
      if (state.status === 'streaming') return
      void runStream({ type: 'action', action, payload })
    },
    [runStream, state.status],
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
              event.data.changed_keys.includes(key)
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

  const uploadDocumentForType = useCallback(
    async (docType: string, file: File) => {
      if (!state.sessionId) return
      const result = await uploadDocument(state.sessionId, docType, file)
      dispatch({ type: 'sse', event: { event: 'ui_card', data: result.card } })
      dispatch({ type: 'sse', event: { event: 'draft', data: result.draft } })
    },
    [dispatch, state.sessionId],
  )

  const removeDocumentForType = useCallback(
    async (docType: string) => {
      if (!state.sessionId) return
      const result = await removeDocument(state.sessionId, docType)
      dispatch({ type: 'sse', event: { event: 'ui_card', data: result.card } })
      dispatch({ type: 'sse', event: { event: 'draft', data: result.draft } })
    },
    [dispatch, state.sessionId],
  )

  const retry = useCallback(() => {
    if (!state.pendingRetry) return
    void runStream(state.pendingRetry)
  }, [runStream, state.pendingRetry])

  const restart = useCallback(async () => {
    abortRef.current?.abort()
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
  }, [dispatch])

  return {
    ...state,
    sendMessage,
    sendAction,
    editReviewField,
    uploadDocument: uploadDocumentForType,
    removeDocument: removeDocumentForType,
    retry,
    restart,
    isStreaming: state.status === 'streaming',
  }
}
