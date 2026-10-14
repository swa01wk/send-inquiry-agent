import styles from './Breadcrumb.module.css'

export function Breadcrumb() {
  return (
    <nav className={styles.nav} aria-label="Breadcrumb">
      <a className={styles.link} href="#sign-in">
        Sign In
      </a>
      <span className={styles.separator} aria-hidden="true">
        ›
      </span>
      <span className={styles.current}>Send Inquiry</span>
    </nav>
  )
}
