import type { DraftChecks } from '../../types/contracts'
import { draftCheckRows } from './draftChecks'
import styles from './ChecksList.module.css'

interface ChecksListProps {
  checks: DraftChecks
}

export function ChecksList({ checks }: ChecksListProps) {
  const rows = draftCheckRows(checks)
  return (
    <section className={styles.section} aria-label="Checks before submit">
      <h3 className={styles.title}>Checks before submit</h3>
      {rows.map((row) => (
        <div key={row.label} className={styles.row}>
          <span className={row.ok ? styles.dotOk : styles.dotNo} aria-hidden="true" />
          <span>{row.label}</span>
        </div>
      ))}
    </section>
  )
}
