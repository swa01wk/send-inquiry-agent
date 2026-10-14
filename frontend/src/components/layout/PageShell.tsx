import type { ReactNode } from 'react'
import { AppHeader } from './AppHeader'
import { Breadcrumb } from './Breadcrumb'
import styles from './PageShell.module.css'

type PageShellProps = {
  children: ReactNode
}

export function PageShell({ children }: PageShellProps) {
  return (
    <>
      <AppHeader />
      <main className={styles.main}>
        <Breadcrumb />
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Send an inquiry</h1>
          <p className={styles.intro}>
            Chat with our leasing assistant. It collects what we need, confirms anything it fills
            in for you, and sends your inquiry to our leasing team.
          </p>
        </div>
        <div className={styles.panels}>{children}</div>
      </main>
    </>
  )
}
