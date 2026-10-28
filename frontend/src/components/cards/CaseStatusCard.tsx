import type { CaseStatusPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './CaseStatusCard.module.css'

interface CaseStatusCardProps {
  payload: CaseStatusPayload
}

function formatLastChange(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function CaseStatusCard({ payload }: CaseStatusCardProps) {
  const lastChange = formatLastChange(payload.last_change)

  return (
    <div className={`${shared.shell} ${styles.shell}`} data-testid="case-status-card">
      <div className={styles.ref}>Reference · {payload.reference}</div>
      <h3 className={styles.stage}>{payload.stage_label}</h3>
      <p className={styles.meta}>
        {payload.owner_role ? `Current owner · ${payload.owner_role}. ` : null}
        Last change · {lastChange}
      </p>
      {payload.open_requests.length > 0 ? (
        <>
          <h4 className={styles.sectionTitle}>Open requests</h4>
          <ul className={styles.requestList}>
            {payload.open_requests.map((req) => (
              <li key={req.id} className={styles.requestItem}>
                <div className={styles.requestLabel}>{req.label}</div>
                {req.remarks ? <p className={styles.requestRemarks}>{req.remarks}</p> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {payload.outcome ? (
        <>
          <h4 className={styles.sectionTitle}>Outcome</h4>
          <p
            className={
              payload.outcome === 'approved' ? styles.outcomeApproved : styles.outcomeRejected
            }
          >
            {payload.outcome === 'approved' ? 'Approved' : 'Rejected'}
          </p>
          {payload.outcome_remarks ? (
            <p className={styles.requestRemarks}>{payload.outcome_remarks}</p>
          ) : null}
        </>
      ) : null}
      <p className={styles.nextStep}>{payload.next_step}</p>
    </div>
  )
}
