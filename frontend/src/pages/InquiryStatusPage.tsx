import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { fetchInquiryStatus } from '../api/client'
import { PageShell } from '../components/layout/PageShell'
import type { InquiryStatusResponse, InquiryStatusStage } from '../types/contracts'
import styles from './inquiryStatus.module.css'

function stageMarkClass(state: InquiryStatusStage['state']): string {
  if (state === 'done') return styles.stepDone
  if (state === 'current') return styles.stepCurrent
  return styles.stepUpcoming
}

export function InquiryStatusPage() {
  const { reference = '' } = useParams()
  const [params] = useSearchParams()
  const token = params.get('t') ?? ''
  const [status, setStatus] = useState<InquiryStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!reference || !token) {
      setError('This tracking link is not valid.')
      setStatus(null)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const data = await fetchInquiryStatus(reference, token)
        if (!cancelled) {
          setStatus(data)
          setError(null)
        }
      } catch (err) {
        if (cancelled) return
        setStatus(null)
        setError(err instanceof Error ? err.message : 'We could not load this inquiry.')
      }
    })()

    return () => {
      cancelled = true
    }
  }, [reference, token])

  const lastChangeLabel =
    status?.last_change != null
      ? new Date(status.last_change).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
      : null

  return (
    <PageShell title="Inquiry status" intro={null} showPanels={false}>
      <div className={styles.card} data-testid="inquiry-status-page">
        {error ? (
          <>
            <h2 className={styles.headline}>Inquiry not found</h2>
            <p className={styles.body}>{error}</p>
            <Link to="/" className={styles.textLink}>
              Send a new inquiry
            </Link>
          </>
        ) : null}
        {!error && !status ? <p className={styles.body}>Loading your inquiry…</p> : null}
        {status ? (
          <>
            <div className={styles.refRow}>
              <span className={styles.refLabel}>Reference</span>
              <span className={styles.refValue}>{status.reference}</span>
            </div>
            <p className={styles.summary}>
              Your inquiry was submitted and is waiting for review.
              {status.owner_role ? ` Current owner: ${status.owner_role}.` : ''}
            </p>
            {lastChangeLabel ? (
              <p className={styles.meta}>Last update · {lastChangeLabel}</p>
            ) : null}
            <h3 className={styles.sectionTitle}>Progress</h3>
            <ol className={styles.timeline}>
              {status.stages.map((stage, index) => (
                <li key={stage.key} className={styles.step}>
                  <span className={stageMarkClass(stage.state)} aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className={styles.stepLabel}>{stage.label}</span>
                </li>
              ))}
            </ol>
            {status.waiting_on_you.length > 0 ? (
              <div className={styles.waiting}>
                <h3 className={styles.sectionTitle}>Waiting on you</h3>
                <ul>
                  {status.waiting_on_you.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </PageShell>
  )
}
