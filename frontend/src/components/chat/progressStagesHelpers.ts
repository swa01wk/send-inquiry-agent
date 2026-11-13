import type { SectionCheck } from '../../types/contracts'
import { PROGRESS_STAGE_LABELS, type ProgressStageKey } from './inquiryProgress'
import type { StageVisualState } from './inquiryProgress'

export function stageLabel(stage: ProgressStageKey, visual: StageVisualState): string {
  const base = PROGRESS_STAGE_LABELS[stage]
  if (visual === 'done') return `✓ ${base}`
  return base
}

export function sectionTabLabel(section: SectionCheck, visual: StageVisualState): string {
  if (visual === 'done') return `✓ ${section.label}`
  return section.label
}
