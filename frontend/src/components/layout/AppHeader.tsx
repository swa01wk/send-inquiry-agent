import styles from './AppHeader.module.css'

export function AppHeader() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brandRow}>
          <span className={styles.wordmark}>cenomi</span>
          <span className={styles.productName}>Tenant Central</span>
        </div>
        <button type="button" className={styles.langButton}>
          العربية
        </button>
      </div>
    </header>
  )
}
