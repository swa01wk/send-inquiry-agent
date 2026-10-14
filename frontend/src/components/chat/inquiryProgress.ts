import type { DraftSummary, Phase } from '../../types/contracts'

export const PROGRESS_STAGE_KEYS = [
  'company',
  'brand',
  'space',
  'contact',
  'documents',
  'review',
] as const

export type ProgressStageKey = (typeof PROGRESS_STAGE_KEYS)[number]

export const PROGRESS_STAGE_LABELS: Record<ProgressStageKey, string> = {
  company: 'Company',
  brand: 'Brand',
  space: 'Space',
  contact: 'Contact',
  documents: 'Documents',
  review: 'Review',
}

const GROUP_ORDER: ProgressStageKey[] = ['company', 'brand', 'space', 'contact']

function groupHasMissingRequired(draft: DraftSummary, group: string): boolean {
  return draft.fields.some(
    (f) => f.group === group && f.required && (f.display == null || f.display === ''),
  )
}

export function currentProgressStage(phase: Phase, draft: DraftSummary | null): ProgressStageKey {
  if (phase === 'submitted') return 'review'
  if (phase === 'review') return 'review'
  if (phase === 'documents') return 'documents'
  if (phase === 'verifying') return 'contact'
  if (phase === 'gate') return 'company'
  if (phase === 'collecting' && draft) {
    for (const group of GROUP_ORDER) {
      if (groupHasMissingRequired(draft, group)) return group
    }
    return 'contact'
  }
  return 'company'
}

export type StageVisualState = 'done' | 'current' | 'upcoming'

export function stageVisualState(
  stage: ProgressStageKey,
  phase: Phase,
  draft: DraftSummary | null,
): StageVisualState {
  if (phase === 'submitted') return 'done'
  const current = currentProgressStage(phase, draft)
  const stageIdx = PROGRESS_STAGE_KEYS.indexOf(stage)
  const currentIdx = PROGRESS_STAGE_KEYS.indexOf(current)
  if (stageIdx < currentIdx) return 'done'
  if (stageIdx === currentIdx) return 'current'
  return 'upcoming'
}
