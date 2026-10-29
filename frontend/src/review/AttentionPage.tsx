import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  approveAttention,
  dismissAttention,
  listAttention,
  streamReviewerAssistant,
  type AttentionItem,
  type AttentionList,
} from '../api/review'
import { StreamAbortError } from '../api/stream'
import type { UiCard } from '../types/contracts'
import { PageShell } from '../components/layout/PageShell'
import { useReviewerId } from './reviewerSession'
import styles from './review.module.css'

function reasonLabel(reason: string): string {
  const text = reason.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isTenantReminderSuggestion(
  card: UiCard,
): card is Extract<UiCard, { card_type: 'reviewer_suggestion' }> {
  return card.card_type === 'reviewer_suggestion' && card.payload.kind === 'tenant_reminder'
}

interface ItemCardProps {
  reviewerId: string
  item: AttentionItem
  reasons: string[]
  busy: boolean
  onApprove: (item: AttentionItem, text: string | undefined) => void
  onDismiss: (item: AttentionItem, reason: string) => void
}

function ItemCard({ reviewerId, item, reasons, busy, onApprove, onDismiss }: ItemCardProps) {
  const [text, setText] = useState(item.text ?? '')
  const [reason, setReason] = useState('')
  const [assistantDraft, setAssistantDraft] = useState<string | null>(null)
  const [drafting, setDrafting] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const isReminder = item.trigger === 'applicant_reminder'

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])
  const tag =
    item.trigger === 'escalation'
      ? styles.tagApplicant
      : isReminder
        ? styles.tagReviewer
        : styles.tag

  return (
    <div className={styles.panel} data-testid={`attention-${item.trigger}-${item.reference}`}>
      <div className={styles.buttonRow}>
        <span className={tag}>{item.label}</span>
        <Link className={styles.link} to={`/review/cases/${item.reference}`}>
          {item.reference}
        </Link>
      </div>
      <p className={styles.muted}>
        {item.brand ?? 'Inquiry'} · {item.mall ?? '—'} · {item.stage_label}
        {item.request_label ? ` · ${item.request_label}` : ''}
      </p>
      <p className={styles.muted} data-testid="attention-age">
        Waiting {Math.floor(item.age_hours)} h (target {item.threshold_hours} h). {item.recommended}
      </p>

      {isReminder && item.status === 'awaiting_approval' ? (
        <>
          <label className={styles.label} htmlFor={`reminder-${item.id}`}>
            Reminder to the applicant
          </label>
          <textarea
            id={`reminder-${item.id}`}
            className={styles.textarea}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className={styles.buttonRow}>
            <button
              type="button"
              className={styles.secondaryBtn}
              data-testid="attention-draft-assistant"
              disabled={busy || drafting}
              onClick={() => {
                void (async () => {
                  setDraftError(null)
                  setAssistantDraft(null)
                  setDrafting(true)
                  abortRef.current?.abort()
                  const controller = new AbortController()
                  abortRef.current = controller
                  const label = item.request_label ?? 'request'
                  let sawSuggestion = false
                  try {
                    await streamReviewerAssistant(
                      reviewerId,
                      item.reference,
                      `Draft a tenant_reminder for the open ${label} on this case.`,
                      (event) => {
                        if (event.event === 'ui_card' && isTenantReminderSuggestion(event.data)) {
                          sawSuggestion = true
                          const remarks = event.data.payload.payload.remarks
                          setAssistantDraft(
                            typeof remarks === 'string' ? remarks : event.data.payload.text,
                          )
                        }
                      },
                      controller.signal,
                    )
                    if (!sawSuggestion) {
                      setDraftError("The assistant couldn't draft this one; edit the text above.")
                    }
                  } catch (err) {
                    if (
                      err instanceof StreamAbortError ||
                      (err instanceof DOMException && err.name === 'AbortError')
                    ) {
                      return
                    }
                    setDraftError("The assistant couldn't draft this one; edit the text above.")
                  } finally {
                    setDrafting(false)
                  }
                })()
              }}
            >
              {drafting ? 'Drafting…' : 'Draft with the assistant'}
            </button>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={busy || !text.trim()}
              onClick={() => onApprove(item, text.trim() === (item.text ?? '') ? undefined : text)}
            >
              Approve and send
            </button>
          </div>
          {assistantDraft ? (
            <div className={styles.suggestionCard} data-testid="attention-assistant-draft">
              <p className={styles.suggestionText}>{assistantDraft}</p>
              <button
                type="button"
                className={styles.secondaryBtn}
                data-testid="attention-use-draft"
                onClick={() => setText(assistantDraft)}
              >
                Use
              </button>
            </div>
          ) : null}
          {draftError ? <p className={styles.muted}>{draftError}</p> : null}
        </>
      ) : null}
      {item.status === 'held' && item.send_after ? (
        <p className={styles.muted} data-testid="attention-held">
          Approved — held until {formatTime(item.send_after)} (quiet hours or the one-message
          limit).
        </p>
      ) : null}

      <div className={styles.buttonRow}>
        <label className={styles.label} htmlFor={`dismiss-${item.id}`}>
          Dismiss because
        </label>
        <select
          id={`dismiss-${item.id}`}
          className={styles.select}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          <option value="">Select…</option>
          {reasons.map((r) => (
            <option key={r} value={r}>
              {reasonLabel(r)}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={styles.secondaryBtn}
          disabled={busy || !reason}
          onClick={() => onDismiss(item, reason)}
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}

/** "Needs attention" (L5 §3.4): flags and drafted reminders for the reviewer's queues. */
export function AttentionPage() {
  const [reviewerId] = useReviewerId()
  const [data, setData] = useState<AttentionList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!reviewerId) return
    try {
      setData(await listAttention(reviewerId))
    } catch {
      setError('Could not load the list.')
    }
  }, [reviewerId])

  useEffect(() => {
    void load()
  }, [load])

  const run = async (work: () => Promise<AttentionItem>, done: (item: AttentionItem) => string) => {
    setBusy(true)
    setError(null)
    try {
      const item = await work()
      setNotice(done(item))
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That didn’t work.')
    } finally {
      setBusy(false)
    }
  }

  if (!reviewerId) {
    return (
      <PageShell title="Needs attention" intro={null} showPanels={false}>
        <p className={styles.muted}>
          <Link className={styles.link} to="/review">
            Sign in as a reviewer
          </Link>{' '}
          first.
        </p>
      </PageShell>
    )
  }

  return (
    <PageShell title="Needs attention" intro={null} showPanels={false}>
      <div className={styles.page} data-testid="attention-page">
        <Link className={styles.link} to="/review">
          ← Back to the queue
        </Link>
        {data ? (
          <p className={styles.muted} data-testid="attention-counts">
            {data.counts.open} open · {data.counts.raised} raised · {data.counts.sent} sent ·{' '}
            {Object.values(data.counts.dismissed).reduce((a, b) => a + b, 0)} dismissed
          </p>
        ) : (
          <p className={styles.muted}>Loading…</p>
        )}
        {notice ? (
          <p className={styles.muted} role="status">
            {notice}
          </p>
        ) : null}
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {data && data.items.length === 0 ? (
          <p className={styles.muted} data-testid="attention-empty">
            Nothing needs your attention right now.
          </p>
        ) : null}
        {data?.items.map((item) => (
          <ItemCard
            key={item.id}
            reviewerId={reviewerId}
            item={item}
            reasons={data.dismiss_reasons}
            busy={busy}
            onApprove={(it, text) =>
              void run(
                () => approveAttention(reviewerId, it.id, text),
                (res) =>
                  res.status === 'sent'
                    ? `Reminder sent for ${res.reference}.`
                    : `Reminder for ${res.reference} approved; held until ${formatTime(res.send_after ?? '')}.`,
              )
            }
            onDismiss={(it, reason) =>
              void run(
                () => dismissAttention(reviewerId, it.id, reason),
                (res) => `Dismissed ${res.reference} (${reasonLabel(reason)}).`,
              )
            }
          />
        ))}
      </div>
    </PageShell>
  )
}
