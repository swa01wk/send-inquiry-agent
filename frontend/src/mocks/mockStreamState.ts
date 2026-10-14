import { draftEmpty } from './fixtures'
import type { DraftSummary } from '../types/contracts'

export let mockDraft: DraftSummary = {
  ...draftEmpty,
  fields: draftEmpty.fields.map((f) => ({ ...f })),
  documents: draftEmpty.documents.map((d) => ({ ...d })),
}

export function resetMockDraft(): void {
  mockDraft = {
    ...draftEmpty,
    fields: draftEmpty.fields.map((f) => ({ ...f })),
    documents: draftEmpty.documents.map((d) => ({ ...d })),
  }
}

export function patchMockDraft(draft: DraftSummary): void {
  mockDraft = draft
}
