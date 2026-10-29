import { API_BASE, E2E_MODE } from '../config'
import { e2eScenarioFromUrl } from './client'
import type { CreateSessionResponse } from '../types/contracts'

/** Call-centre console (spec §15). */

export interface StaffMember {
  id: string
  name: string
  role: 'customer_care' | 'guest_service' | string
  role_label: string
}

export interface HandoffItem {
  case_id: string
  inquiry_id: string
  short_ref: string
  reason: string
  reason_label: string
  summary: string
  created_at: string
}

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

function staffHeaders(staffId: string, extra: Record<string, string> = {}): Record<string, string> {
  return { 'X-Staff-Id': staffId, ...extra }
}

export async function listStaff(): Promise<StaffMember[]> {
  const res = await fetch(`${API_BASE}/api/callcentre/staff`)
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<StaffMember[]>
}

export async function newInquiry(staffId: string): Promise<CreateSessionResponse> {
  const headers = staffHeaders(staffId)
  if (E2E_MODE) {
    const scenario = e2eScenarioFromUrl()
    if (scenario) headers['X-Test-Scenario'] = scenario
  }

  const res = await fetch(`${API_BASE}/api/callcentre/inquiries`, { method: 'POST', headers })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}

export async function listHandoffs(staffId: string): Promise<HandoffItem[]> {
  const res = await fetch(`${API_BASE}/api/callcentre/handoffs`, {
    headers: staffHeaders(staffId),
  })
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<HandoffItem[]>
}

export async function openHandoff(staffId: string, caseId: string): Promise<CreateSessionResponse> {
  const res = await fetch(
    `${API_BASE}/api/callcentre/handoffs/${encodeURIComponent(caseId)}/open`,
    {
      method: 'POST',
      headers: staffHeaders(staffId),
    },
  )
  if (!res.ok) {
    const err = await parseError(res)
    throw Object.assign(new Error(err.message), { code: err.code })
  }
  return res.json() as Promise<CreateSessionResponse>
}
