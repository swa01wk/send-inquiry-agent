import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE, E2E_MODE } from '../config'
import { e2eScenarioFromUrl } from './client'
import type { SseEvent } from '../types/contracts'
import { StreamAbortError } from './stream'

/** Reviewer console API (L4 §3.3). Every call carries the mock reviewer identity. */

export interface Reviewer {
  id: string
  name: string
  role: string
  regions: string[]
  manager: boolean
}

export type WaitingOn = 'reviewer' | 'applicant' | 'system' | 'nobody'

export interface QueueItem {
  reference: string
  brand: string | null
  company: string | null
  mall: string | null
  product_line: string | null
  region: string | null
  status: string
  stage_label: string
  waiting_on: WaitingOn
  age_days: number
  last_change: string
  open_requests: string[]
  possible_duplicate: boolean
  follow_on_of: string | null
  needs_operations: boolean
  channel?: string
  staff_role?: string | null
}

export interface BriefField {
  key: string
  label: string
  group: string
  display: string | null
  source: 'user' | 'derived' | 'verified' | 'default' | null
  confirmed: boolean
  evidence: string | null
}

export interface BriefDocument {
  doc_type: string
  label: string
  required: boolean
  uploaded: boolean
  file_id: string | null
  file_name: string | null
  size_bytes: number | null
  uploaded_at: string | null
  replaced_versions: number
}

export interface BriefRequest {
  id: string
  kind: 'reupload' | 'contacts' | 'sales_data'
  status: 'open' | 'fulfilled' | 'withdrawn'
  remarks: string
  doc_types: string[]
  requested_by: string
  requested_at: string
  closed_at: string | null
}

export interface BriefDecision {
  level: 'first' | 'second'
  outcome: 'approved' | 'rejected'
  remarks: string | null
  reason_category: string | null
  by: string
  at: string
}

export interface BriefContact {
  role: string
  label: string
  name: string | null
  email: string | null
  phone: string | null
  same_as_primary: boolean
}

export interface CaseBrief {
  reference: string
  status: string
  stage_label: string
  waiting_on: WaitingOn
  queue_role: string | null
  queue_region: string | null
  channel: string
  staff_role?: string | null
  company: string | null
  brand: string | null
  product_line: string | null
  mall: string | null
  region: string | null
  cr_status: string
  submitted_at: string
  fields: BriefField[]
  verification: Record<string, boolean>
  documents: BriefDocument[]
  sales_data: BriefDocument | null
  contacts: BriefContact[]
  requests: BriefRequest[]
  decisions: BriefDecision[]
  follow_on_of: string | null
  yardi: {
    company_id: string | null
    brand_id: string | null
    lead_ref: string | null
    attempts: number
    needs_operations: boolean
  }
  stage_ages: { stage: string; entered_at: string; days: number }[]
  next_decision_checklist: string[]
}

export interface TimelineEntry {
  at: string
  actor: string
  type: string
  summary: string
}

export type ReviewAction =
  | 'request_reupload'
  | 'reject'
  | 'approve_first'
  | 'request_contacts'
  | 'request_sales_data'
  | 'withdraw_request'
  | 'relink_company'
  | 'relink_brand'
  | 'remove_contact'
  | 'approve'

export interface CaseDetail {
  brief: CaseBrief
  timeline: TimelineEntry[]
  legal_actions: ReviewAction[]
  approval_blockers: string[]
  rejection_categories: string[]
  reupload_doc_types: { doc_type: string; label: string }[]
}

export class ReviewApiError extends Error {
  code: string
  status: number
  constructor(status: number, code: string, message: string) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request(
  path: string,
  reviewerId: string | null,
  init: RequestInit = {},
): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  if (reviewerId) headers['X-Reviewer-Id'] = reviewerId
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let code = 'request_failed'
    let message = 'Request failed'
    try {
      const body = (await res.json()) as { error?: { code: string; message: string } }
      if (body.error) ({ code, message } = body.error)
    } catch {
      /* keep the defaults */
    }
    throw new ReviewApiError(res.status, code, message)
  }
  return res
}

export async function listReviewers(): Promise<Reviewer[]> {
  return (await request('/api/review/reviewers', null)).json() as Promise<Reviewer[]>
}

export async function listCases(reviewerId: string, waitingOn?: WaitingOn): Promise<QueueItem[]> {
  const query = waitingOn ? `?waiting_on=${waitingOn}` : ''
  return (await request(`/api/review/cases${query}`, reviewerId)).json() as Promise<QueueItem[]>
}

export async function getCase(reviewerId: string, reference: string): Promise<CaseDetail> {
  const res = await request(`/api/review/cases/${encodeURIComponent(reference)}`, reviewerId)
  return res.json() as Promise<CaseDetail>
}

export async function actOnCase(
  reviewerId: string,
  reference: string,
  action: ReviewAction,
  payload: Record<string, unknown>,
): Promise<CaseDetail> {
  const res = await request(
    `/api/review/cases/${encodeURIComponent(reference)}/actions`,
    reviewerId,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, payload }),
    },
  )
  return res.json() as Promise<CaseDetail>
}

export interface YardiCompany {
  id: string
  name: string
}

export interface YardiBrand {
  id: string
  name: string
  source: 'lease' | 'proposal' | string
}

/** Options for `relink_company`: active Yardi companies by the first word of the name. */
export async function searchYardiCompanies(
  reviewerId: string,
  query: string,
): Promise<YardiCompany[]> {
  const res = await request(
    `/api/review/yardi/companies?q=${encodeURIComponent(query)}`,
    reviewerId,
  )
  return res.json() as Promise<YardiCompany[]>
}

/** Options for `relink_brand`: the linked company's brands. */
export async function listYardiBrands(
  reviewerId: string,
  companyId: string,
): Promise<YardiBrand[]> {
  const res = await request(
    `/api/review/yardi/companies/${encodeURIComponent(companyId)}/brands`,
    reviewerId,
  )
  return res.json() as Promise<YardiBrand[]>
}

/** Download needs the reviewer header, so it goes through fetch and a blob URL. */
function parseReviewerSse(eventType: string, data: string): SseEvent | null {
  if (!eventType || !data) return null
  try {
    const parsed = JSON.parse(data) as SseEvent['data']
    return { event: eventType, data: parsed } as SseEvent
  } catch {
    return null
  }
}

export type ReviewerStreamOutcome = 'ok' | 'error'

/** SSE over POST for the reviewer assistant (same events as applicant chat). */
export async function streamReviewerAssistant(
  reviewerId: string,
  reference: string,
  text: string,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<ReviewerStreamOutcome> {
  let sawError = false
  const path = `/api/review/cases/${encodeURIComponent(reference)}/assistant`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
    'X-Reviewer-Id': reviewerId,
  }
  if (E2E_MODE) {
    const scenario = e2eScenarioFromUrl()
    if (scenario) headers['X-Test-Scenario'] = scenario
  }

  await fetchEventSource(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text }),
    signal,
    openWhenHidden: true,
    async onopen(res) {
      if (res.ok && res.headers.get('content-type')?.includes('text/event-stream')) {
        return
      }
      if (res.status === 401) {
        throw Object.assign(new Error('Unknown reviewer'), { code: 'unknown_reviewer' })
      }
      if (res.status === 404) {
        throw Object.assign(new Error('Case not found'), { code: 'case_not_found' })
      }
      let code = 'stream_failed'
      let message = 'Stream failed'
      try {
        const errBody = (await res.json()) as { error?: { code: string; message: string } }
        if (errBody.error) {
          code = errBody.error.code
          message = errBody.error.message
        }
      } catch {
        /* ignore */
      }
      throw Object.assign(new Error(message), { code })
    },
    onmessage(msg) {
      const event = parseReviewerSse(msg.event, msg.data)
      if (event) {
        if (event.event === 'error') sawError = true
        onEvent(event)
      }
    },
    onerror(err) {
      if (signal.aborted) throw new StreamAbortError()
      throw err
    },
  })

  return sawError ? 'error' : 'ok'
}

export async function downloadDocument(
  reviewerId: string,
  reference: string,
  fileId: string,
  fileName: string,
): Promise<void> {
  const res = await request(
    `/api/review/cases/${encodeURIComponent(reference)}/documents/${encodeURIComponent(fileId)}`,
    reviewerId,
  )
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

/** "Needs attention" (L5): proactive items for the reviewer's queues. */
export interface AttentionItem {
  id: string
  trigger: 'stalled_review' | 'escalation' | 'applicant_reminder'
  label: string
  recommended: string
  reference: string
  brand: string | null
  mall: string | null
  stage_label: string
  status: 'open' | 'awaiting_approval' | 'held' | 'sent' | 'dismissed'
  audience: 'queue' | 'manager'
  tier: number
  age_hours: number
  threshold_hours: number
  request_kind: string | null
  request_label: string | null
  text: string | null
  raised_at: string
  send_after: string | null
  sent_at: string | null
  dismissed_reason: string | null
}

export interface AttentionList {
  items: AttentionItem[]
  counts: { open: number; raised: number; sent: number; dismissed: Record<string, number> }
  dismiss_reasons: string[]
}

export async function listAttention(reviewerId: string): Promise<AttentionList> {
  return (await request('/api/review/attention', reviewerId)).json() as Promise<AttentionList>
}

export async function approveAttention(
  reviewerId: string,
  itemId: string,
  text?: string,
): Promise<AttentionItem> {
  const res = await request(
    `/api/review/attention/${encodeURIComponent(itemId)}/approve`,
    reviewerId,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(text === undefined ? {} : { text }),
    },
  )
  return res.json() as Promise<AttentionItem>
}

export async function dismissAttention(
  reviewerId: string,
  itemId: string,
  reason: string,
): Promise<AttentionItem> {
  const res = await request(
    `/api/review/attention/${encodeURIComponent(itemId)}/dismiss`,
    reviewerId,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    },
  )
  return res.json() as Promise<AttentionItem>
}
