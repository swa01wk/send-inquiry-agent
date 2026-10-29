import { useCallback, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { flushSync } from 'react-dom'
import { streamReviewerAssistant } from '../api/review'
import { StreamAbortError } from '../api/stream'
import type { ReviewerSuggestionPayload, UiCard } from '../types/contracts'
import styles from './review.module.css'

interface ChatLine {
  id: string
  role: 'user' | 'assistant'
  text: string
  cards: UiCard[]
}

interface ReviewerAssistantPanelProps {
  reviewerId: string
  reference: string
  onUseSuggestion: (payload: ReviewerSuggestionPayload) => void
}

function isReviewerSuggestion(
  card: UiCard,
): card is Extract<UiCard, { card_type: 'reviewer_suggestion' }> {
  return card.card_type === 'reviewer_suggestion'
}

function SuggestionCard({
  payload,
  onUse,
}: {
  payload: ReviewerSuggestionPayload
  onUse: () => void
}) {
  const canUse = payload.action !== '' && payload.kind !== 'tenant_reminder'
  return (
    <div className={styles.suggestionCard} data-testid="reviewer-suggestion">
      <p className={styles.suggestionText}>{payload.text}</p>
      {canUse ? (
        <button type="button" className={styles.secondaryBtn} onClick={onUse}>
          Use
        </button>
      ) : null}
    </div>
  )
}

/** Case-page assistant: typed messages and suggestion cards over POST SSE. */
export function ReviewerAssistantPanel({
  reviewerId,
  reference,
  onUseSuggestion,
}: ReviewerAssistantPanelProps) {
  const [lines, setLines] = useState<ChatLine[]>([])
  const [draft, setDraft] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const assistantIdRef = useRef<string | null>(null)
  const streamTextRef = useRef('')

  const send = useCallback(
    async (text: string) => {
      if (streaming) return
      setStreamError(null)
      const userId = `user-${Date.now()}`
      const assistantId = `assistant-${Date.now()}`
      assistantIdRef.current = assistantId
      streamTextRef.current = ''
      flushSync(() => {
        setLines((prev) => [
          ...prev,
          { id: userId, role: 'user', text, cards: [] },
          { id: assistantId, role: 'assistant', text: '', cards: [] },
        ])
        setStreaming(true)
      })
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamReviewerAssistant(
          reviewerId,
          reference,
          text,
          (event) => {
            if (event.event === 'token') {
              const { message_id, text: chunk } = event.data
              streamTextRef.current += chunk
              assistantIdRef.current = message_id
              const textSoFar = streamTextRef.current
              setLines((prev) =>
                prev.map((line) =>
                  line.role === 'assistant' && line.id === assistantId
                    ? { ...line, id: message_id, text: textSoFar }
                    : line.id === message_id
                      ? { ...line, text: textSoFar }
                      : line,
                ),
              )
            } else if (event.event === 'ui_card' && isReviewerSuggestion(event.data)) {
              const card = event.data
              setLines((prev) => {
                let target = -1
                for (let i = prev.length - 1; i >= 0; i -= 1) {
                  if (prev[i].role === 'assistant') {
                    target = i
                    break
                  }
                }
                if (target < 0) return prev
                return prev.map((line, i) =>
                  i === target ? { ...line, cards: [...line.cards, card] } : line,
                )
              })
            } else if (event.event === 'error') {
              setStreamError(event.data.message)
            }
          },
          controller.signal,
        )
      } catch (err) {
        if (
          err instanceof StreamAbortError ||
          (err instanceof DOMException && err.name === 'AbortError')
        ) {
          return
        }
        setStreamError(err instanceof Error ? err.message : 'Could not reach the assistant.')
      } finally {
        setStreaming(false)
      }
    },
    [reference, reviewerId, streaming],
  )

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed || streaming) return
    setDraft('')
    void send(trimmed)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const trimmed = draft.trim()
      if (!trimmed || streaming) return
      setDraft('')
      void send(trimmed)
    }
  }

  return (
    <section
      className={styles.panel}
      aria-labelledby="assistant-title"
      data-testid="reviewer-assistant-panel"
    >
      <h2 id="assistant-title" className={styles.panelTitle}>
        Assistant
      </h2>
      <p className={styles.muted}>
        Ask about this case or draft remarks. Suggestions fill the action forms — they never submit
        for you.
      </p>
      <div className={styles.assistantLog} aria-live="polite" data-testid="assistant-log">
        {lines.length === 0 ? (
          <p className={styles.muted}>No messages yet.</p>
        ) : (
          lines.map((line) => (
            <div
              key={line.id}
              className={line.role === 'user' ? styles.assistantUserLine : styles.assistantBotLine}
              data-testid={line.role === 'assistant' ? 'assistant-reply' : 'assistant-user'}
            >
              {line.text ? <p className={styles.assistantText}>{line.text}</p> : null}
              {line.cards.map((card) =>
                isReviewerSuggestion(card) ? (
                  <SuggestionCard
                    key={card.card_id}
                    payload={card.payload}
                    onUse={() => onUseSuggestion(card.payload)}
                  />
                ) : null,
              )}
            </div>
          ))
        )}
      </div>
      {streamError ? (
        <p className={styles.error} role="alert">
          {streamError}
        </p>
      ) : null}
      <form className={styles.assistantForm} onSubmit={onSubmit}>
        <label className={styles.label} htmlFor="assistant-input">
          Message
        </label>
        <textarea
          id="assistant-input"
          className={styles.textarea}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask the assistant…"
          disabled={streaming}
          rows={2}
        />
        <button type="submit" className={styles.primaryBtn} disabled={streaming || !draft.trim()}>
          {streaming ? 'Thinking…' : 'Send'}
        </button>
      </form>
    </section>
  )
}
