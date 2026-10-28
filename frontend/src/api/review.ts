import { API_BASE } from '../config'

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
