import type { DuplicateNoticePayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './DuplicateNoticeCard.module.css'

interface DuplicateNoticeCardProps {
  payload: DuplicateNoticePayload
}

/** Chart S15: one neutral line, from code; the agent doesn't repeat it unless asked. */
export function DuplicateNoticeCard({ payload }: DuplicateNoticeCardProps) {
  return (
    <div
      className={`${shared.shellPad} ${styles.layout}`}
      data-testid="duplicate-notice-card"
      data-policy={payload.policy}
      role="note"
    >
      <p className={styles.message}>{payload.message}</p>
    </div>
  )
}
