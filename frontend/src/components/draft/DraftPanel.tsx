import { useEffect, useRef, useState } from 'react'
import type { DraftSummary } from '../../types/contracts'
import { useChatStore } from '../../state/chatStore'
import { BadgeLegend } from './BadgeLegend'
import { ChecksList } from './ChecksList'
import { DRAFT_GROUP_ORDER, draftGroupTitle, firstChangedKeyInPanelOrder } from './draftGroups'
import { DraftGroup } from './DraftGroup'
import styles from './DraftPanel.module.css'

const FLASH_MS = 1800
const SCROLL_OFFSET_PX = 12

function prefersReducedMotion(): boolean {
  if (typeof window.matchMedia !== 'function') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

interface DraftPanelViewProps {
  draft: DraftSummary | null
}

/** Presentational panel; exported for tests with a fixed draft. */
export function DraftPanelView({ draft }: DraftPanelViewProps) {
  const bodyRef = useRef<HTMLDivElement>(null)
  const [flashKeys, setFlashKeys] = useState<Set<string>>(() => new Set())

  const checks = draft?.checks
  const filled = checks?.required_filled ?? 0
  const total = checks?.required_total ?? 11
  const progressPct = total > 0 ? Math.min(100, (filled / total) * 100) : 0

  useEffect(() => {
    const keys = draft?.changed_keys ?? []
    if (keys.length === 0 || !draft) return

    setFlashKeys(new Set(keys))
    const flashTimer = window.setTimeout(() => setFlashKeys(new Set()), FLASH_MS)

    const firstKey = firstChangedKeyInPanelOrder(draft.fields, keys)
    const body = bodyRef.current
    if (firstKey && body) {
      const row = body.querySelector<HTMLElement>(`#draft-${CSS.escape(firstKey)}`)
      if (row) {
        const top = Math.max(0, row.offsetTop - SCROLL_OFFSET_PX)
        if (typeof body.scrollTo === 'function') {
          body.scrollTo({
            top,
            behavior: prefersReducedMotion() ? 'auto' : 'smooth',
          })
        } else {
          body.scrollTop = top
        }
      }
    }

    return () => window.clearTimeout(flashTimer)
  }, [draft])

  return (
    <aside className={styles.panel} aria-label="Inquiry draft">
      <div className={styles.header}>
        <h2 className={styles.title}>Inquiry draft</h2>
        <p className={styles.description}>
          What the agent has collected so far, and where each value came from.
        </p>
        <div className={styles.progressRow}>
          <span className={styles.progressLabel}>Required fields</span>
          <span className={styles.progressCount} data-testid="draft-progress-count">
            {filled} of {total}
          </span>
        </div>
        <div className={styles.track} aria-hidden="true">
          <div
            className={styles.fill}
            data-testid="draft-progress-fill"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
      <div ref={bodyRef} className={styles.body} data-testid="draft-scroll-body">
        {DRAFT_GROUP_ORDER.map((groupId) => (
          <DraftGroup
            key={groupId}
            title={draftGroupTitle(groupId)}
            fields={draft?.fields.filter((f) => f.group === groupId) ?? []}
            flashKeys={flashKeys}
          />
        ))}
        {checks ? <ChecksList checks={checks} /> : null}
        <BadgeLegend />
      </div>
    </aside>
  )
}

export function DraftPanel() {
  const { state } = useChatStore()
  return <DraftPanelView draft={state.draft} />
}
