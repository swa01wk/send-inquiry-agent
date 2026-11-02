import type { DraftSummary } from '../../types/contracts'
import { nextStepStripStep } from './inquiryProgress'

export function shouldShowNextStepStrip({
  draft,
  phase,
  assistedIntake,
  formModeActive,
}: {
  draft: DraftSummary | null
  phase: DraftSummary['phase']
  assistedIntake?: boolean
  formModeActive?: boolean
}): boolean {
  if (!draft || phase === 'submitted' || assistedIntake || formModeActive) return false
  const step = nextStepStripStep(draft.checks.next_step)
  if (!step) return false
  if (draft.checks.next_step === 'cr' || draft.checks.next_step === 'fields') return false
  return true
}
