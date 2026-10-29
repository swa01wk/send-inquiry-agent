import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  actOnCase,
  downloadDocument,
  getCase,
  ReviewApiError,
  type BriefField,
  type CaseDetail,
  type ReviewAction,
} from '../api/review'
import { PageShell } from '../components/layout/PageShell'
import { ActionsPanel, type ActionsPrefill } from './ActionsPanel'
import { prefillFromSuggestion } from './prefillFromSuggestion'
import { ReviewerAssistantPanel } from './ReviewerAssistantPanel'
import {
  ROLE_LABELS,
  channelLabel,
  regionLabel,
  useReviewerId,
  waitingOnLabel,
} from './reviewerSession'
import styles from './review.module.css'

const SOURCE_LABELS: Record<string, string> = {
  user: 'Typed',
  derived: 'Derived',
  verified: 'Verified (CR)',
  default: 'Default',
}

const GROUP_TITLES: Record<string, string> = {
  company: 'Company',
  brand: 'Brand',
  space: 'Space',
  contact: 'Contact',
  documents: 'Document numbers',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function SourceTag({ field }: { field: BriefField }) {
  if (!field.source) return null
  const text = `${SOURCE_LABELS[field.source] ?? field.source}${
    field.source === 'user' || field.source === 'default'
      ? ''
      : field.confirmed
        ? ' · confirmed'
        : ' · not confirmed'
  }`
  const style =
    field.source === 'derived'
      ? styles.tagReviewer
      : field.source === 'verified'
        ? styles.tagDone
        : styles.tag
  return (
    <span className={field.confirmed || field.source === 'user' ? style : styles.tagApplicant}>
      {text}
    </span>
  )
}

/** One case: the brief, documents, requests, the audit timeline and the legal actions. */
export function ReviewCasePage() {
  const { reference = '' } = useParams()
  const [reviewerId] = useReviewerId()
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionsPrefill, setActionsPrefill] = useState<ActionsPrefill | undefined>()

  useEffect(() => {
    if (!reviewerId) return
    let cancelled = false
    getCase(reviewerId, reference)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setLoadError(
          err instanceof ReviewApiError && err.status === 404
            ? 'This case is not in your queues.'
            : 'Could not load the case.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [reviewerId, reference])

  const onAct = useCallback(
    async (action: ReviewAction, payload: Record<string, unknown>) => {
      if (!reviewerId) return
      setBusy(true)
      setActionError(null)
      try {
        setDetail(await actOnCase(reviewerId, reference, action, payload))
      } catch (err) {
        setActionError(err instanceof Error ? err.message : 'That action failed.')
      } finally {
        setBusy(false)
      }
    },
    [reviewerId, reference],
  )

  if (!reviewerId) {
    return (
      <PageShell title="Case" intro={null} showPanels={false}>
        <p className={styles.muted}>
          <Link className={styles.link} to="/review">
            Sign in as a reviewer
          </Link>{' '}
          to open this case.
        </p>
      </PageShell>
    )
  }

  if (loadError || !detail) {
    return (
      <PageShell title={reference} intro={null} showPanels={false}>
        <div className={styles.page}>
          <Link className={styles.link} to="/review">
            ← Back to the queue
          </Link>
          <p className={loadError ? styles.error : styles.muted}>{loadError ?? 'Loading…'}</p>
        </div>
      </PageShell>
    )
  }

  const brief = detail.brief
  const groups = Object.keys(GROUP_TITLES).filter((g) =>
    brief.fields.some((f) => f.group === g && f.display),
  )

  return (
    <PageShell title={brief.reference} intro={null} showPanels={false}>
      <div className={styles.page} data-testid="review-case-page">
        <Link className={styles.link} to="/review">
          ← Back to the queue
        </Link>
        <div className={styles.layout}>
          <div className={styles.column}>
            <section className={styles.panel} aria-labelledby="summary-title">
              <h2 id="summary-title" className={styles.panelTitle}>
                {brief.brand ?? 'Inquiry'} · {brief.company ?? 'company not given'}
              </h2>
              <div className={styles.summaryGrid}>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Stage</span>
                  <span className={styles.summaryValue} data-testid="case-stage">
                    {brief.stage_label}
                  </span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Waiting on</span>
                  <span className={styles.summaryValue}>{waitingOnLabel(brief.waiting_on)}</span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Queue</span>
                  <span className={styles.summaryValue}>
                    {brief.queue_role ? (ROLE_LABELS[brief.queue_role] ?? brief.queue_role) : '—'} ·{' '}
                    {regionLabel(brief.queue_region)}
                  </span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Mall</span>
                  <span className={styles.summaryValue}>{brief.mall ?? '—'}</span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Channel</span>
                  <span className={styles.summaryValue} data-testid="case-channel">
                    {channelLabel(brief.channel, brief.staff_role) ?? 'Applicant (self-service)'}
                  </span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>CR</span>
                  <span className={styles.summaryValue}>{brief.cr_status}</span>
                </div>
                <div className={styles.summaryItem}>
                  <span className={styles.summaryLabel}>Submitted</span>
                  <span className={styles.summaryValue}>{formatTime(brief.submitted_at)}</span>
                </div>
              </div>
              {brief.next_decision_checklist.length > 0 ? (
                <ul className={styles.list} data-testid="checklist">
                  {brief.next_decision_checklist.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
              {brief.follow_on_of ? (
                <p className={styles.muted}>Follow-on of {brief.follow_on_of}</p>
              ) : null}
            </section>

            <section className={styles.panel} aria-labelledby="fields-title">
              <h2 id="fields-title" className={styles.panelTitle}>
                Details and where they came from
              </h2>
              {groups.map((group) => (
                <div key={group}>
                  <h3 className={styles.actionTitle}>{GROUP_TITLES[group]}</h3>
                  {brief.fields
                    .filter((f) => f.group === group && f.display)
                    .map((field) => (
                      <div key={field.key} className={styles.fieldRow}>
                        <span className={styles.fieldLabel}>{field.label}</span>
                        <span className={styles.fieldValue}>{field.display}</span>
                        <SourceTag field={field} />
                        {field.evidence ? (
                          <span className={styles.evidence}>from: “{field.evidence}”</span>
                        ) : null}
                      </div>
                    ))}
                </div>
              ))}
              <p className={styles.muted}>
                Email {brief.verification.email_verified ? 'verified' : 'not verified'} · Mobile{' '}
                {brief.verification.mobile_verified ? 'verified' : 'not verified'}
              </p>
            </section>

            <section className={styles.panel} aria-labelledby="docs-title">
              <h2 id="docs-title" className={styles.panelTitle}>
                Documents
              </h2>
              <ul className={styles.list}>
                {[...brief.documents, ...(brief.sales_data ? [brief.sales_data] : [])].map(
                  (doc) => (
                    <li key={doc.doc_type}>
                      {doc.label}
                      {doc.required ? ' (required)' : ''}:{' '}
                      {doc.uploaded && doc.file_id ? (
                        <button
                          type="button"
                          className={styles.secondaryBtn}
                          onClick={() =>
                            void downloadDocument(
                              reviewerId,
                              brief.reference,
                              doc.file_id as string,
                              doc.file_name ?? doc.doc_type,
                            )
                          }
                        >
                          {doc.file_name}
                        </button>
                      ) : (
                        <span className={styles.muted}>not uploaded</span>
                      )}
                      {doc.replaced_versions > 0 ? (
                        <span className={styles.muted}> · replaced {doc.replaced_versions}×</span>
                      ) : null}
                    </li>
                  ),
                )}
              </ul>
            </section>

            <section className={styles.panel} aria-labelledby="requests-title">
              <h2 id="requests-title" className={styles.panelTitle}>
                Requests and decisions
              </h2>
              {brief.requests.length === 0 && brief.decisions.length === 0 ? (
                <p className={styles.muted}>None yet.</p>
              ) : null}
              <ul className={styles.list} data-testid="requests">
                {brief.requests.map((r) => (
                  <li key={r.id}>
                    <strong>{r.kind.replace('_', ' ')}</strong> · {r.status} ·{' '}
                    {formatTime(r.requested_at)}
                    {r.remarks ? ` — “${r.remarks}”` : ''}
                  </li>
                ))}
                {brief.decisions.map((d) => (
                  <li key={`${d.level}-${d.at}`}>
                    <strong>
                      {d.level} level {d.outcome}
                    </strong>{' '}
                    · {formatTime(d.at)}
                    {d.remarks ? ` — “${d.remarks}”` : ''}
                  </li>
                ))}
              </ul>
              {brief.contacts.length > 0 ? (
                <>
                  <h3 className={styles.actionTitle}>Tenant contacts</h3>
                  <ul className={styles.list}>
                    {brief.contacts.map((c) => (
                      <li key={c.role}>
                        {c.label}: {c.name ?? '—'}, {c.email ?? '—'}, {c.phone ?? '—'}
                        {c.same_as_primary ? ' (primary contact)' : ''}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
              {brief.yardi.lead_ref ? (
                <p className={styles.muted}>Sent to Yardi: {brief.yardi.lead_ref}</p>
              ) : null}
            </section>

            <section className={styles.panel} aria-labelledby="timeline-title">
              <h2 id="timeline-title" className={styles.panelTitle}>
                Audit timeline
              </h2>
              <ol className={styles.timeline} data-testid="timeline">
                {detail.timeline.map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className={styles.timelineItem}>
                    <span className={styles.timelineTime}>{formatTime(entry.at)}</span>
                    <span className={styles.timelineActor}>{entry.actor}</span>
                    <span>{entry.summary}</span>
                  </li>
                ))}
              </ol>
            </section>
          </div>
          <div className={styles.column}>
            <ReviewerAssistantPanel
              reviewerId={reviewerId}
              reference={reference}
              onUseSuggestion={(payload) => setActionsPrefill(prefillFromSuggestion(payload))}
            />
            <ActionsPanel
              detail={detail}
              reviewerId={reviewerId}
              busy={busy}
              error={actionError}
              prefill={actionsPrefill}
              onAct={(action, payload) => void onAct(action, payload)}
            />
          </div>
        </div>
      </div>
    </PageShell>
  )
}
