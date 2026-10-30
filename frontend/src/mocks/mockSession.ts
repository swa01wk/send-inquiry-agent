import {
  defaultMockSessionCards,
  documentUploadCardExample,
  MOCK_WELCOME_MESSAGES,
} from './fixtures'
import { getActiveJsonScenario, resetScenarioTurnState } from './scenarios/load'
import { resetDemoMessageCounter } from './scenarios/demo'
import { mockDraft, patchMockDraft, resetMockDraft } from './mockStreamState'
import type { CreateSessionResponse, DraftSummary, UiCard } from '../types/contracts'

export function resetMockSessionState(): void {
  resetMockDraft()
  resetScenarioTurnState()
  resetDemoMessageCounter()
}

export async function mockCreateSession(): Promise<CreateSessionResponse> {
  resetMockSessionState()
  const json = getActiveJsonScenario()
  if (json) {
    patchMockDraft(json.session.draft)
    return {
      session_id: json.session.session_id,
      messages: json.session.messages.map((m) => ({ ...m })),
      cards: json.session.cards.map((c) => ({ ...c })),
      draft: JSON.parse(JSON.stringify(json.session.draft)) as DraftSummary,
    }
  }
  return {
    session_id: 'mock-session',
    messages: MOCK_WELCOME_MESSAGES.map((m) => ({ ...m })),
    cards: defaultMockSessionCards(),
    draft: { ...mockDraft },
  }
}

function documentCardFromDraft(draft: DraftSummary): UiCard {
  const base = documentUploadCardExample
  if (base.card_type !== 'document_upload') return base
  return {
    ...base,
    payload: {
      ...base.payload,
      docs: draft.documents.map((d) => ({ ...d })),
      required_uploaded: draft.checks.required_docs_uploaded,
      required_total: draft.checks.required_docs_total,
    },
  }
}

export async function mockUploadDocument(
  docType: string,
  file: File,
): Promise<{ card: UiCard; draft: DraftSummary }> {
  const ext = file.name.includes('.')
    ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    : ''
  const uploadPayload =
    documentUploadCardExample.card_type === 'document_upload'
      ? documentUploadCardExample.payload
      : null
  if (!uploadPayload) {
    throw Object.assign(new Error('Upload unavailable'), { code: 'unknown_doc_type' })
  }
  const allowed = uploadPayload.allowed_extensions
  if (!allowed.includes(ext)) {
    throw Object.assign(new Error("That file type isn't supported."), { code: 'invalid_extension' })
  }
  if (file.size > uploadPayload.max_mb * 1024 * 1024) {
    throw Object.assign(new Error('That file is over 5 MB.'), { code: 'too_large' })
  }

  const documents = mockDraft.documents.map((d) => {
    if (d.doc_type !== docType) return d
    return {
      ...d,
      uploaded: true,
      file_name: file.name,
      size_bytes: file.size,
    }
  })
  const requiredUploaded = documents.filter((d) => d.required && d.uploaded).length
  const next: DraftSummary = {
    ...mockDraft,
    documents,
    checks: {
      ...mockDraft.checks,
      required_docs_uploaded: requiredUploaded,
    },
    changed_keys: [docType],
  }
  patchMockDraft(next)
  return { card: documentCardFromDraft(next), draft: next }
}

export async function mockRemoveDocument(
  docType: string,
): Promise<{ card: UiCard; draft: DraftSummary }> {
  const documents = mockDraft.documents.map((d) => {
    if (d.doc_type !== docType) return d
    return { ...d, uploaded: false, file_name: null, size_bytes: null }
  })
  const requiredUploaded = documents.filter((d) => d.required && d.uploaded).length
  const next: DraftSummary = {
    ...mockDraft,
    documents,
    checks: {
      ...mockDraft.checks,
      required_docs_uploaded: requiredUploaded,
    },
    changed_keys: [docType],
  }
  patchMockDraft(next)
  return { card: documentCardFromDraft(next), draft: next }
}
