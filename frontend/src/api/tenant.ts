import { API_BASE } from '../config'
import type { CreateSessionResponse } from '../types/contracts'

/** Simulated Tenant Central (spec §15): every call carries the mock tenant identity. */

export interface TenantSummary {
  id: string
  company_name: string
  contact_name: string
  brands: { id: string; name: string }[]
}

export interface Opportunity {
  id: string
  mall_id: string
  mall: string
  city_id: string
  city: string
  unit_type: string
  unit_type_label: string
  unit_ref: string
  area_min: number
  area_max: number
}

export interface MyInquiry {
  reference: string
  brand: string | null
  mall: string | null
  product_line: string | null
  stage_label: string
  submitted_at: string
  last_change: string
  tracking_url: string
}

export class TenantApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request(path: string, tenantId: string | null, init: RequestInit = {}) {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  if (tenantId) headers['X-Tenant-Id'] = tenantId
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let message = 'Request failed'
    try {
      const body = (await res.json()) as { error?: { message: string } }
      if (body.error) message = body.error.message
    } catch {
      /* keep the default */
    }
    throw new TenantApiError(res.status, message)
  }
  return res
}

export async function listTenants(): Promise<TenantSummary[]> {
  return (await request('/api/tenant/tenants', null)).json() as Promise<TenantSummary[]>
}

export async function listOpportunities(tenantId: string): Promise<Opportunity[]> {
  return (await request('/api/tenant/opportunities', tenantId)).json() as Promise<Opportunity[]>
}

export async function raiseInquiry(
  tenantId: string,
  opportunityId: string,
  brandId?: string,
): Promise<CreateSessionResponse> {
  const res = await request(
    `/api/tenant/opportunities/${encodeURIComponent(opportunityId)}/inquiry`,
    tenantId,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(brandId ? { brand_id: brandId } : {}),
    },
  )
  return res.json() as Promise<CreateSessionResponse>
}

export async function listMyInquiries(tenantId: string): Promise<MyInquiry[]> {
  return (await request('/api/tenant/inquiries', tenantId)).json() as Promise<MyInquiry[]>
}
