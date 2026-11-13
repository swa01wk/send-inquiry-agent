import type { InformTenantPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './ContactCheckCard.module.css'

interface InformTenantCardProps {
  payload: InformTenantPayload
  onSendSignInLink: () => void
}

/** Flow v2 (§3.4, E5): the caller already has an account — what to say, and the sign-in email. */
export function InformTenantCard({ payload, onSendSignInLink }: InformTenantCardProps) {
  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="inform-tenant-card">
      <p className={styles.prompt}>{payload.title}</p>
      <p className={styles.say} data-testid="inform-tenant-say">
        {payload.say}
      </p>

      {payload.error ? (
        <p className={styles.error} role="alert">
          {payload.error}
        </p>
      ) : null}

      {payload.sent ? (
        <p className={styles.doneLine}>Sign-in link sent to {payload.email_masked}</p>
      ) : payload.offer_sign_in_link ? (
        <button type="button" className={shared.primaryBtnFull} onClick={onSendSignInLink}>
          {payload.sign_in_label}
        </button>
      ) : null}
    </div>
  )
}
