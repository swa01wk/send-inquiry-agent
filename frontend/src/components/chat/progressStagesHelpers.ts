import { PROGRESS_STAGE_LABELS, stageVisualState, type ProgressStageKey } from './inquiryProgress'

export function stageLabel(
  key: ProgressStageKey,
  visual: ReturnType<typeof stageVisualState>,
): string {
  const label = PROGRESS_STAGE_LABELS[key]
  if (visual === 'done') return `✓ ${label}`
  return label
}

/** Alias used in tests and prompts. */
export const stageText = stageLabel
