import { API_BASE, E2E_MODE, MOCK_MODE } from '../config'
import { mockCreateSession, mockRemoveDocument, mockUploadDocument } from '../mocks/mockSession'
import type {
  CreateSessionResponse,
  DraftSummary,
  InquiryStatusResponse,
  OutboxMessage,
  UiCard,
  VerifyEmailResponse,
} from '../types/contracts'

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

function e2eScenarioFromUrl(): string | undefined {
  if (typeof window === 'undefined') return undefined
  return new URLSearchParams(window.location.search).get('e2eScenario') ?? undefined
}

export async function createSession(): Promise<CreateSessionResponse> {
  if (MOCK_MODE) return mockCreateSession()

  const headers: Record<string, string> = {}
  if (E2E_MODE) {
    const scenario = e2eScenarioFromUrl()
    if (scenario) headers['X-Test-Scenario'] = scenario
  }

  const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST', headers })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}

export type MasterListItem =
  | { id: string; label: string }
  | { id: string; name: string; city?: string }
  | { id: string; label: string; code?: string }

export async function fetchMasterKind(kind: string): Promise<MasterListItem[]> {
  if (MOCK_MODE) {
    return []
  }

  const res = await fetch(`${API_BASE}/api/master/${kind}`)
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<MasterListItem[]>
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

export async function verifyEmailLink(token: string): Promise<VerifyEmailResponse> {
  const res = await fetch(`${API_BASE}/api/verifications/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<VerifyEmailResponse>
}

export async function resumeSession(token: string): Promise<CreateSessionResponse> {
  const res = await fetch(`${API_BASE}/api/sessions/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}

export async function openCase(token: string): Promise<CreateSessionResponse> {
  const res = await fetch(`${API_BASE}/api/cases/open`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}

export async function fetchInquiryStatus(
  reference: string,
  trackToken: string,
): Promise<InquiryStatusResponse> {
  const url = new URL(`${API_BASE}/api/inquiries/${encodeURIComponent(reference)}`)
  url.searchParams.set('t', trackToken)
  const res = await fetch(url.toString())
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<InquiryStatusResponse>
}

export async function fetchOutbox(to?: string): Promise<OutboxMessage[]> {
  const url = new URL(`${API_BASE}/api/dev/outbox`)
  if (to) url.searchParams.set('to', to)
  const res = await fetch(url.toString())
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  const body = (await res.json()) as { messages: OutboxMessage[] }
  return body.messages
}

export async function clearOutbox(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/dev/outbox`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
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
