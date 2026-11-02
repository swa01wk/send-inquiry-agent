import type { DraftSummary, Phase } from '../../types/contracts'
import type { ChatMessage } from '../../state/chatStore'
import type { UiCard } from '../../types/contracts'
import {
  PROGRESS_STAGE_KEYS,
  PROGRESS_STAGE_LABELS,
  stageTabEnabled,
  stageVisualState,
  type ProgressStageKey,
} from './inquiryProgress'

export type { ProgressStageKey } from './inquiryProgress'
import styles from './ProgressStages.module.css'

interface ProgressStagesProps {
  phase: Phase
  draft: DraftSummary | null
  cards: Record<string, UiCard>
  messages: ChatMessage[]
  onStageClick?: (stage: ProgressStageKey) => void
}

export function stageLabel(
  key: ProgressStageKey,
  visual: ReturnType<typeof stageVisualState>,
): string {
  const label = PROGRESS_STAGE_LABELS[key]
  if (visual === 'done') return `✓ ${label}`
  return label
}

// Re-export for tests that import stageText naming from prompt
export { stageLabel as stageText }

export function ProgressStages({
  phase,
  draft,
  cards,
  messages,
  onStageClick,
}: ProgressStagesProps) {
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
