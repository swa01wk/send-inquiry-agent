import type { ConfirmFieldsPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import shared from './cards.module.css'
import styles from './ConfirmFieldsCard.module.css'

interface ConfirmFieldsCardProps {
  cardId: string
  payload: ConfirmFieldsPayload
  onConfirm: () => void
}

export function ConfirmFieldsCard({ cardId, payload, onConfirm }: ConfirmFieldsCardProps) {
  return (
    <div className={shared.shellRows} data-testid={`confirm-fields-${cardId}`}>
      {payload.fields.map((field, index) => (
        <div
          key={field.key}
          className={`${styles.row} ${index < payload.fields.length - 1 || !payload.all_confirmed ? shared.rowDivider : ''}`}
        >
          <span className={styles.label}>{field.label}</span>
          <span className={styles.value}>{field.display ?? '—'}</span>
          <SourceBadge source={field.source} confirmed={field.confirmed} />
        </div>
      ))}
      {!payload.all_confirmed ? (
        <div className={styles.footer}>
          <button type="button" className={shared.textLink} onClick={onConfirm}>
            Looks right
          </button>
        </div>
      ) : null}
    </div>
  )
}
