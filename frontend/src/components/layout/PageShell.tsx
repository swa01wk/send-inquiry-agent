import type { ReactNode } from 'react'
import { AppHeader } from './AppHeader'
import { Breadcrumb } from './Breadcrumb'
import styles from './PageShell.module.css'

type PageShellProps = {
  children: ReactNode
  title?: string
  intro?: string | null
  showPanels?: boolean
}

export function PageShell({
  children,
  title = 'Send an inquiry',
  intro = 'Chat with our leasing assistant. It collects what we need, confirms anything it fills in for you, and sends your inquiry to our leasing team.',
  showPanels = true,
}: PageShellProps) {
  return (
    <>
      <AppHeader />
      <main className={styles.main}>
        <Breadcrumb />
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>{title}</h1>
          {intro ? <p className={styles.intro}>{intro}</p> : null}
        </div>
        <div className={showPanels ? styles.panels : styles.singlePanel}>{children}</div>
      </main>
    </>
  )
}
