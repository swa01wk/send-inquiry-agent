import styles from './TypingIndicator.module.css'

export function TypingIndicator() {
  return (
    <div className={styles.row} aria-label="Assistant is typing" role="status">
      <div className={styles.avatar} aria-hidden="true">
        C
      </div>
      <div className={styles.bubble}>
        <span className={styles.dot} />
        <span className={styles.dot} />
        <span className={styles.dot} />
      </div>
    </div>
  )
}
