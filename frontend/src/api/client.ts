import { API_BASE, MOCK_MODE } from '../config'
import { mockCreateSession, mockRemoveDocument, mockUploadDocument } from '../mocks/mockSession'
import type { CreateSessionResponse, DraftSummary, UiCard } from '../types/contracts'

interface ApiErrorBody {
  error?: { code: string; message: string }
}

async function parseError(res: Response): Promise<{ code: string; message: string }> {
  try {
    const body = (await res.json()) as ApiErrorBody
    if (body.error) return body.error
  } catch {
    /* ignore */
  }
  return { code: 'request_failed', message: 'Request failed' }
}

export async function createSession(): Promise<CreateSessionResponse> {
  if (MOCK_MODE) return mockCreateSession()

  const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}

export async function fetchDraft(sessionId: string): Promise<DraftSummary> {
  if (MOCK_MODE) {
    const session = await mockCreateSession()
    return session.draft
  }

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/draft`)
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<DraftSummary>
}

export interface DocumentMutationResponse {
  card: UiCard
  draft: DraftSummary
  document?: { doc_type: string; file_name: string; size_bytes: number }
}

export async function uploadDocument(
  sessionId: string,
  docType: string,
  file: File,
): Promise<DocumentMutationResponse> {
  if (MOCK_MODE) return mockUploadDocument(docType, file)

  const form = new FormData()
  form.append('doc_type', docType)
  form.append('file', file)

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/documents`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<DocumentMutationResponse>
}

export async function removeDocument(
  sessionId: string,
  docType: string,
): Promise<DocumentMutationResponse> {
  if (MOCK_MODE) return mockRemoveDocument(docType)

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/documents/${docType}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<DocumentMutationResponse>
}
