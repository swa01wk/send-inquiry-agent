import type { DraftFieldRow } from '../../types/contracts'
import { SourceBadge } from './SourceBadge'
import styles from './DraftRow.module.css'

interface DraftRowProps {
  field: DraftFieldRow
  flash: boolean
}

export function DraftRow({ field, flash }: DraftRowProps) {
  const hasValue = Boolean(field.display)
  return (
    <div
      id={`draft-${field.key}`}
      className={`${styles.row} ${flash ? styles.flash : ''}`}
      data-testid={`draft-row-${field.key}`}
    >
      <div className={styles.labelRow}>
        <span className={styles.label}>{field.label}</span>
        {field.source ? <SourceBadge source={field.source} confirmed={field.confirmed} /> : null}
      </div>
      <span className={hasValue ? styles.value : styles.valueEmpty}>
        {hasValue ? field.display : 'Not yet collected'}
      </span>
    </div>
  )
}
