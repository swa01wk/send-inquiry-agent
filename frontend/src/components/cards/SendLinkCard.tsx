import type { SendLinkPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './SendLinkCard.module.css'

interface SendLinkCardProps {
  payload: SendLinkPayload
  onSendLink: () => void
}

export function SendLinkCard({ payload, onSendLink }: SendLinkCardProps) {
  const sent = payload.sent_to_masked != null && payload.sent_to_masked !== ''

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="send-link-card">
      <p className={styles.emailLine}>Applicant email: {payload.email_masked ?? '—'}</p>
      {payload.missing.length > 0 ? (
        <p className={styles.missing}>Still needed: {payload.missing.join(', ')}</p>
      ) : null}
      {sent ? <p className={styles.sentLine}>Link sent to {payload.sent_to_masked}</p> : null}
      <button
        type="button"
        className={shared.primaryBtnFull}
        disabled={!payload.can_send}
        onClick={onSendLink}
      >
        {sent ? 'Resend link' : 'Send application link'}
      </button>
    </div>
  )
}
