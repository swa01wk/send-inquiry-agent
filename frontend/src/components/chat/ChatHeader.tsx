import { DEMO_MODE, MOCK_MODE } from '../../config'
import type { DraftSummary, Phase } from '../../types/contracts'
import { ProgressStages } from './ProgressStages'
import styles from './ChatHeader.module.css'

interface ChatHeaderProps {
  phase: Phase
  draft: DraftSummary | null
  draftPanelVisible: boolean
  onToggleDraftPanel: () => void
  onRestart: () => void
}

const showRestart = DEMO_MODE || import.meta.env.DEV || MOCK_MODE

export function ChatHeader({
  phase,
  draft,
  draftPanelVisible,
  onToggleDraftPanel,
  onRestart,
}: ChatHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.top}>
        <div className={styles.identity}>
          <div className={styles.avatar} aria-hidden="true">
            C
          </div>
          <div>
            <h2 className={styles.title}>Cenomi leasing assistant</h2>
            <p className={styles.subtitle}>Leasing inquiries for new brands</p>
          </div>
        </div>
        <div className={styles.actions}>
          {showRestart ? (
            <>
              <button type="button" className={styles.restart} onClick={onToggleDraftPanel}>
                {draftPanelVisible ? 'Hide draft' : 'Show draft'}
              </button>
              <button type="button" className={styles.restart} onClick={onRestart}>
                Restart
              </button>
            </>
          ) : null}
        </div>
      </div>
      <ProgressStages phase={phase} draft={draft} />
    </header>
  )
}
