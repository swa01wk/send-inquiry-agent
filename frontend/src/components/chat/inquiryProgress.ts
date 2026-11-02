import type { ChatMessage } from '../../state/chatStore'
import type {
  DraftFieldRow,
  DraftSummary,
  Phase,
  RemainingStep,
  UiCard,
} from '../../types/contracts'

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

const FIELD_GROUP_ORDER: ProgressStageKey[] = ['company', 'brand', 'space', 'contact']

function contactRequiredFields(draft: DraftSummary) {
  return draft.fields.filter((f) => f.group === 'contact' && f.required)
}

function groupRequiredFields(draft: DraftSummary, group: string) {
  return draft.fields.filter((f) => f.group === group && f.required)
}

function fieldRowComplete(row: DraftFieldRow): boolean {
  return row.display != null && row.display !== '' && row.confirmed
}

function crPending(draft: DraftSummary): boolean {
  return draft.checks.remaining.includes('cr')
}

function groupCollectingComplete(draft: DraftSummary, group: string): boolean {
  if (group === 'contact') {
    const rows = contactRequiredFields(draft)
    const hasPhone = draft.fields.some(
      (f) =>
        (f.key === 'mobile' || f.key === 'landline') &&
        f.display != null &&
        f.display !== '' &&
        f.confirmed,
    )
    return rows.every(fieldRowComplete) && hasPhone
  }
  return groupRequiredFields(draft, group).every(fieldRowComplete)
}

export function companyStageDone(draft: DraftSummary): boolean {
  if (crPending(draft)) return false
  return groupCollectingComplete(draft, 'company')
}

export function brandStageDone(draft: DraftSummary): boolean {
  return groupCollectingComplete(draft, 'brand')
}

export function spaceStageDone(draft: DraftSummary): boolean {
  return groupCollectingComplete(draft, 'space')
}

export function contactStageDone(draft: DraftSummary): boolean {
  return groupCollectingComplete(draft, 'contact') && draft.checks.contact_verified
}

export function documentsStageDone(draft: DraftSummary): boolean {
  const { required_docs_uploaded, required_docs_total } = draft.checks
  return required_docs_uploaded >= required_docs_total && required_docs_total > 0
}

export function reviewStageDone(phase: Phase): boolean {
  return phase === 'submitted'
}

export function stageIsDone(stage: ProgressStageKey, phase: Phase, draft: DraftSummary): boolean {
  if (phase === 'submitted') return true
  switch (stage) {
    case 'company':
      return companyStageDone(draft)
    case 'brand':
      return brandStageDone(draft)
    case 'space':
      return spaceStageDone(draft)
    case 'contact':
      return contactStageDone(draft)
    case 'documents':
      return documentsStageDone(draft)
    case 'review':
      return reviewStageDone(phase)
    default:
      return false
  }
}

function firstFieldGapGroup(draft: DraftSummary): ProgressStageKey {
  for (const group of FIELD_GROUP_ORDER) {
    if (!groupCollectingComplete(draft, group)) return group
  }
  return 'contact'
}

export function currentProgressStage(phase: Phase, draft: DraftSummary | null): ProgressStageKey {
  if (!draft) return 'company'
  if (phase === 'submitted') return 'review'
  const step: RemainingStep | null = draft.checks.next_step
  if (!step) {
    return phase === 'review' ? 'review' : 'review'
  }
  if (step === 'cr') return 'company'
  if (step === 'fields') return firstFieldGapGroup(draft)
  if (step === 'verify_email' || step === 'verify_mobile') return 'contact'
  if (step === 'documents') return 'documents'
  if (step === 'terms') return 'review'
  return 'company'
}

export type StageVisualState = 'done' | 'current' | 'upcoming'

export function stageVisualState(
  stage: ProgressStageKey,
  phase: Phase,
  draft: DraftSummary | null,
): StageVisualState {
  if (!draft) return stage === 'company' ? 'current' : 'upcoming'
  if (stageIsDone(stage, phase, draft)) return 'done'
  const current = currentProgressStage(phase, draft)
  if (stage === current) return 'current'
  return 'upcoming'
}

const CONFIRM_GROUP: Record<ProgressStageKey, string | null> = {
  company: 'company',
  brand: 'brand',
  space: 'space',
  contact: null,
  documents: null,
  review: null,
}

function cardIdsInTranscript(messages: ChatMessage[]): string[] {
  return messages.flatMap((m) => m.cardIds)
}

function confirmCardMatchesGroup(card: UiCard, group: string, draft: DraftSummary): boolean {
  if (card.card_type !== 'confirm_fields') return false
  return card.payload.fields.some((f) => {
    const row = draft.fields.find((d) => d.key === f.key)
    return row?.group === group
  })
}

export function latestConfirmCardIdForGroup(
  group: string,
  draft: DraftSummary,
  cards: Record<string, UiCard>,
  messages: ChatMessage[],
): string | null {
  const ids = cardIdsInTranscript(messages)
  for (let i = ids.length - 1; i >= 0; i -= 1) {
    const card = cards[ids[i]]
    if (card && confirmCardMatchesGroup(card, group, draft)) return card.card_id
  }
  return null
}

export function stageScrollTarget(
  stage: ProgressStageKey,
  draft: DraftSummary,
  cards: Record<string, UiCard>,
  messages: ChatMessage[],
): { kind: 'selector'; selector: string } | { kind: 'card'; cardId: string } | null {
  if (stage === 'contact') {
    return Object.values(cards).some((c) => c.card_type === 'verification')
      ? { kind: 'selector', selector: '[data-testid="verification-card"]' }
      : null
  }
  if (stage === 'documents') {
    return Object.values(cards).some((c) => c.card_type === 'document_upload')
      ? { kind: 'selector', selector: '[data-testid="document-checklist-card"]' }
      : null
  }
  if (stage === 'review') {
    return Object.values(cards).some((c) => c.card_type === 'review')
      ? { kind: 'selector', selector: '[data-testid="review-card"]' }
      : null
  }
  const group = CONFIRM_GROUP[stage]
  if (!group) return null
  const cardId = latestConfirmCardIdForGroup(group, draft, cards, messages)
  return cardId ? { kind: 'card', cardId } : null
}

export function stageTabEnabled(
  stage: ProgressStageKey,
  draft: DraftSummary,
  cards: Record<string, UiCard>,
  messages: ChatMessage[],
): boolean {
  return stageScrollTarget(stage, draft, cards, messages) != null
}

export function nextStepStripStep(
  next: RemainingStep | null,
): 'verify_email' | 'verify_mobile' | 'documents' | 'terms' | null {
  if (
    next === 'verify_email' ||
    next === 'verify_mobile' ||
    next === 'documents' ||
    next === 'terms'
  ) {
    return next
  }
  return null
}

export const NEXT_STEP_STRIP_COPY: Record<
  Exclude<ReturnType<typeof nextStepStripStep>, null>,
  string
> = {
  verify_email: 'Next: open the link we emailed you',
  verify_mobile: 'Next: enter the SMS code',
  documents: 'Next: upload the required documents',
  terms: 'Next: review and submit',
}
