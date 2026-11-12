import type { DraftSummary, Phase } from '../../types/contracts'
import type { ChatMessage } from '../../state/chatStore'
import type { UiCard } from '../../types/contracts'
import {
  PROGRESS_STAGE_KEYS,
  stageTabEnabled,
  stageVisualState,
  type ProgressStageKey,
} from './inquiryProgress'
import { sectionTabLabel, stageLabel } from './progressStagesHelpers'
import styles from './ProgressStages.module.css'

export type { ProgressStageKey } from './inquiryProgress'

interface ProgressStagesProps {
  phase: Phase
  draft: DraftSummary | null
  cards: Record<string, UiCard>
  messages: ChatMessage[]
  onStageClick?: (stage: ProgressStageKey) => void
}

function sectionVisual(
  section: { key: string; done: boolean },
  draft: DraftSummary | null,
): 'done' | 'current' | 'upcoming' {
  if (section.done) return 'done'
  if (draft?.section === section.key) return 'current'
  return 'upcoming'
}

export function ProgressStages({
  phase,
  draft,
  cards,
  messages,
  onStageClick,
}: ProgressStagesProps) {
  const sections = draft?.checks.sections ?? []
  if (sections.length > 0) {
    return (
      <div className={styles.track} aria-label="Inquiry progress">
        {sections.map((section) => {
          const visual = sectionVisual(section, draft)
          const label = sectionTabLabel(section, visual)
          return (
            <span
              key={section.key}
              className={styles.pill}
              data-state={visual}
              data-testid={`stage-${section.key}`}
            >
              {label}
            </span>
          )
        })}
      </div>
    )
  }

  return (
    <div className={styles.track} aria-label="Inquiry progress">
      {PROGRESS_STAGE_KEYS.map((key) => {
        const visual = stageVisualState(key, phase, draft)
        const enabled = draft ? stageTabEnabled(key, draft, cards, messages) : false
        const label = stageLabel(key, visual)
        if (enabled && onStageClick) {
          return (
            <button
              key={key}
              type="button"
              className={styles.pill}
              data-state={visual}
              data-testid={`stage-${key}`}
              onClick={() => onStageClick(key)}
            >
              {label}
            </button>
          )
        }
        return (
          <span
            key={key}
            className={styles.pill}
            data-state={visual}
            data-testid={`stage-${key}`}
            aria-disabled={!enabled}
          >
            {label}
          </span>
        )
      })}
    </div>
  )
}
