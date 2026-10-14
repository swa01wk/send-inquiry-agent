import { SourceBadge } from './SourceBadge'
import styles from './BadgeLegend.module.css'

export function BadgeLegend() {
  return (
    <section className={styles.section} aria-label="Source badges">
      <h3 className={styles.title}>Source badges</h3>
      <div className={styles.items}>
        <SourceBadge source="user" confirmed />
        <SourceBadge source="verified" confirmed />
        <SourceBadge source="derived" confirmed={false} />
        <SourceBadge source="derived" confirmed />
        <SourceBadge source="default" confirmed />
      </div>
    </section>
  )
}
