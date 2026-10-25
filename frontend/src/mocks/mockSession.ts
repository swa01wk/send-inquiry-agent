import { documentUploadCardExample, quickRepliesCardExample } from './fixtures'
import { mockDraft, patchMockDraft, resetMockDraft } from './mockStreamState'
import type { CreateSessionResponse, DraftSummary, UiCard } from '../types/contracts'

const WELCOME_1 = "Marhaba, and welcome to Cenomi Tenant Central! I'm your leasing assistant."
const WELCOME_2 =
  "I'll help you send a leasing inquiry in a few minutes, no long form. To start, do you have your company's CR number? I'll check whether you already have an account with us."

export function resetMockSessionState(): void {
  resetMockDraft()
}

export async function mockCreateSession(): Promise<CreateSessionResponse> {
  resetMockSessionState()
  return {
    session_id: 'mock-session',
    messages: [
      { id: 'welcome-1', role: 'assistant', text: WELCOME_1 },
      { id: 'welcome-2', role: 'assistant', text: WELCOME_2 },
    ],
    cards: [{ ...quickRepliesCardExample, message_id: 'welcome-2' }],
    draft: mockDraft,
  }
}

function patchDraft(next: DraftSummary): DraftSummary {
  patchMockDraft(next)
  return next
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
  patchDraft(next)
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
  patchDraft(next)
  return { card: documentCardFromDraft(next), draft: next }
}
