import type { DraftSummary, Phase } from '../../types/contracts'
import {
  PROGRESS_STAGE_KEYS,
  PROGRESS_STAGE_LABELS,
  stageVisualState,
  type ProgressStageKey,
} from './inquiryProgress'
import styles from './ProgressStages.module.css'

interface ProgressStagesProps {
  phase: Phase
  draft: DraftSummary | null
}

function stageText(key: ProgressStageKey, visual: ReturnType<typeof stageVisualState>): string {
  const label = PROGRESS_STAGE_LABELS[key]
  if (visual === 'done') return `✓ ${label}`
  return label
}

export function ProgressStages({ phase, draft }: ProgressStagesProps) {
  return (
    <div className={styles.track} aria-label="Inquiry progress">
      {PROGRESS_STAGE_KEYS.map((key) => {
        const visual = stageVisualState(key, phase, draft)
        return (
          <span
            key={key}
            className={styles.pill}
            data-state={visual}
            data-testid={`stage-${key}`}
          >
            {stageText(key, visual)}
          </span>
        )
      })}
    </div>
  )
}
