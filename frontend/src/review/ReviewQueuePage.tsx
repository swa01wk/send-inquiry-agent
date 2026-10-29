import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  listAttention,
  listCases,
  listReviewers,
  type QueueItem,
  type Reviewer,
  type WaitingOn,
} from '../api/review'
import { PageShell } from '../components/layout/PageShell'
import {
  ROLE_LABELS,
  channelLabel,
  regionLabel,
  useReviewerId,
  waitingOnLabel,
} from './reviewerSession'
import styles from './review.module.css'

function waitingTag(waitingOn: string): string {
  if (waitingOn === 'reviewer') return styles.tagReviewer
  if (waitingOn === 'applicant') return styles.tagApplicant
  return styles.tag
}

/** Mock sign-in (pick a reviewer), then the reviewer's queue (L4 §3.3). */
export function ReviewQueuePage() {
  const [reviewerId, setReviewerId] = useReviewerId()
  const [reviewers, setReviewers] = useState<Reviewer[]>([])
  const [choice, setChoice] = useState('')
  const [cases, setCases] = useState<QueueItem[] | null>(null)
  const [filter, setFilter] = useState<WaitingOn | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [attentionCount, setAttentionCount] = useState<number | null>(null)
  const [params, setParams] = useSearchParams()
  const asReviewer = params.get('as')

  // `/review?as=<id>`: the dev landing page opens a queue in one click (mock sign-in).
  // The parameter is dropped once used, so "Switch reviewer" still works.
  useEffect(() => {
    if (!asReviewer) return
    setReviewerId(asReviewer)
    setParams({}, { replace: true })
  }, [asReviewer, setReviewerId, setParams])

  useEffect(() => {
    let cancelled = false
    listReviewers()
      .then((rows) => {
        if (!cancelled) setReviewers(rows)
      })
      .catch(() => {
        if (!cancelled) setError('The reviewer console is not available.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!reviewerId) return
    let cancelled = false
    setCases(null)
    listCases(reviewerId, filter || undefined)
      .then((rows) => {
        if (!cancelled) setCases(rows)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your queue.')
      })
    return () => {
      cancelled = true
    }
  }, [reviewerId, filter])

  useEffect(() => {
    if (!reviewerId) return
    let cancelled = false
    listAttention(reviewerId)
      .then((data) => {
        if (!cancelled) setAttentionCount(data.counts.open)
      })
      .catch(() => {
        if (!cancelled) setAttentionCount(null)
      })
    return () => {
      cancelled = true
    }
  }, [reviewerId])

  const me = reviewers.find((r) => r.id === reviewerId) ?? null

  if (!reviewerId || !me) {
    return (
      <PageShell
        title="Reviewer console"
        intro="Sign in as a reviewer (simulated)."
        showPanels={false}
      >
        <div className={styles.page}>
          <div className={styles.panel} data-testid="reviewer-sign-in">
            <label className={styles.label} htmlFor="reviewer-picker">
              Reviewer
            </label>
            <select
              id="reviewer-picker"
              className={styles.select}
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
            >
              <option value="">Select a reviewer…</option>
              {reviewers.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} — {ROLE_LABELS[r.role] ?? r.role},{' '}
                  {r.manager ? 'all regions (manager)' : r.regions.map(regionLabel).join(', ')}
                </option>
              ))}
            </select>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={!choice}
                onClick={() => setReviewerId(choice)}
              >
                Sign in
              </button>
            </div>
            {error ? <p className={styles.error}>{error}</p> : null}
          </div>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell title="Review queue" intro={null} showPanels={false}>
      <div className={styles.page}>
        <div className={styles.bar}>
          <p className={styles.who} data-testid="signed-in-reviewer">
            Signed in as <span className={styles.whoName}>{me.name}</span> ·{' '}
            {ROLE_LABELS[me.role] ?? me.role} ·{' '}
            {me.manager ? 'all regions' : me.regions.map(regionLabel).join(', ')}
          </p>
          <div className={styles.buttonRow}>
            <Link className={styles.link} to="/review/attention" data-testid="attention-link">
              Needs attention
              {attentionCount !== null ? (
                <span
                  className={attentionCount > 0 ? styles.tagApplicant : styles.tag}
                  data-testid="attention-badge"
                >
                  {attentionCount}
                </span>
              ) : null}
            </Link>
            <label className={styles.label} htmlFor="waiting-filter">
              Waiting on
            </label>
            <select
              id="waiting-filter"
              className={styles.select}
              value={filter}
              onChange={(e) => setFilter(e.target.value as WaitingOn | '')}
            >
              <option value="">Everyone</option>
              <option value="reviewer">You</option>
              <option value="applicant">Applicant</option>
            </select>
            <button
              type="button"
              className={styles.secondaryBtn}
              onClick={() => setReviewerId(null)}
            >
              Switch reviewer
            </button>
          </div>
        </div>
        {error ? <p className={styles.error}>{error}</p> : null}
        <div className={styles.card}>
          {cases === null ? <p className={styles.muted}>Loading…</p> : null}
          {cases !== null && cases.length === 0 ? (
            <p className={styles.muted} data-testid="queue-empty">
              No cases in your queue.
            </p>
          ) : null}
          {cases !== null && cases.length > 0 ? (
            <div className={styles.tableWrap}>
              <table className={styles.table} data-testid="queue-table">
                <thead>
                  <tr>
                    <th scope="col">Reference</th>
                    <th scope="col">Brand</th>
                    <th scope="col">Mall</th>
                    <th scope="col">Stage</th>
                    <th scope="col">Waiting on</th>
                    <th scope="col">Age</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.reference} data-testid={`queue-row-${c.reference}`}>
                      <td>
                        <Link className={styles.link} to={`/review/cases/${c.reference}`}>
                          {c.reference}
                        </Link>
                        {c.follow_on_of ? (
                          <div className={styles.muted}>Follow-on of {c.follow_on_of}</div>
                        ) : null}
                        {channelLabel(c.channel) ? (
                          <div>
                            <span className={styles.tag} data-testid="channel-label">
                              {channelLabel(c.channel)}
                            </span>
                          </div>
                        ) : null}
                      </td>
                      <td>{c.brand ?? '—'}</td>
                      <td>{c.mall ?? '—'}</td>
                      <td>
                        {c.stage_label}
                        {c.needs_operations ? (
                          <div>
                            <span className={styles.tagApplicant}>Yardi: needs operations</span>
                          </div>
                        ) : null}
                      </td>
                      <td>
                        <span className={waitingTag(c.waiting_on)}>
                          {waitingOnLabel(c.waiting_on)}
                        </span>
                      </td>
                      <td>{c.age_days < 1 ? 'Today' : `${Math.floor(c.age_days)} d`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </PageShell>
  )
}
