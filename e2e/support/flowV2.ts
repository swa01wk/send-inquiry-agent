import { expect, type APIRequestContext } from '@playwright/test'

const API = 'http://127.0.0.1:8000'

/**
 * Flow v2 helpers (docs/specs/flow-v2-alignment.md). F1: reviewer actions through the console
 * API and the tracking page's stages. F2 adds `expectFlowPath` (chart steps, spec §3.1) and the
 * dev seed endpoint.
 */
export async function reviewerAct(
  request: APIRequestContext,
  reviewerId: string,
  reference: string,
  action: string,
  payload: Record<string, unknown> = {},
): Promise<void> {
  const res = await request.post(
    `${API}/api/review/cases/${encodeURIComponent(reference)}/actions`,
    { headers: { 'X-Reviewer-Id': reviewerId }, data: { action, payload } },
  )
  expect(res.ok(), await res.text()).toBeTruthy()
}

/** The tracking page's stages for `reference`, read with the link from the submission email. */
export async function trackingStages(
  request: APIRequestContext,
  trackingLink: string,
): Promise<{ key: string; label: string; state: string }[]> {
  const url = new URL(trackingLink)
  const reference = url.pathname.split('/').pop() ?? ''
  const token = url.searchParams.get('t') ?? ''
  const res = await request.get(`${API}/api/inquiries/${encodeURIComponent(reference)}`, {
    params: { t: token },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  const body = (await res.json()) as { stages: { key: string; label: string; state: string }[] }
  return body.stages
}

export type FlowStep = { node: string; outcome: string | null; actor: string | null }

/** The chart steps recorded for a reference or session (GET /api/dev/flow/{id}, spec §3.1). */
export async function flowPath(
  request: APIRequestContext,
  id: string,
): Promise<{ status: string | null; path: string[]; steps: FlowStep[] }> {
  const res = await request.get(`${API}/api/dev/flow/${encodeURIComponent(id)}`)
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as { status: string | null; path: string[]; steps: FlowStep[] }
}

/** Connectors and boxes outside the POC (scenarios.json `ignored_nodes`). */
const IGNORED_NODES = new Set(['A1', 'A2', 'A3', 'B1', 'B2', 'reg1', 'reg2'])

/**
 * The catalogue's path rule: each chart path, minus the ignored nodes, appears in order (as
 * a subsequence) in the recorded path; `notPath` nodes don't appear at all.
 */
export async function expectFlowPath(
  request: APIRequestContext,
  id: string,
  chartPaths: string[][],
  notPath: string[] = [],
): Promise<void> {
  const { path } = await flowPath(request, id)
  for (const chartPath of chartPaths) {
    let at = 0
    for (const node of chartPath.filter((n) => !IGNORED_NODES.has(n))) {
      const found = path.indexOf(node, at)
      const where = `"${node}" of [${chartPath.join(' → ')}] in [${path.join(', ')}]`
      expect(found, where).toBeGreaterThanOrEqual(0)
      at = found + 1
    }
  }
  for (const node of notPath) {
    expect(path, `"${node}" must not be on the path`).not.toContain(node)
  }
}

export type FlowSeed = {
  reference: string
  case_id: string
  status: string
  applicant_email: string
  first_reviewer: string | null
  final_reviewer: string | null
}

/** A case at `stage`, built by the real events (POST /api/dev/flow/seed). */
export async function seedFlowCase(
  request: APIRequestContext,
  stage: 'submitted' | 'qualified' | 'lead_approved',
  options: { unit_type?: string; malls?: string[] } = {},
): Promise<FlowSeed> {
  const res = await request.post(`${API}/api/dev/flow/seed`, { data: { stage, ...options } })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as FlowSeed
}

/**
 * The tenant's side of a case request without the case chat (F2 backbone; the case-agent
 * scripts on the Cursor track drive the same steps in the UI): open the case link, upload
 * the Forecasted Sales Data and send it.
 */
export async function tenantSendsSalesData(
  request: APIRequestContext,
  caseLink: string,
  file: { name: string; buffer: Buffer; mimeType?: string },
): Promise<void> {
  const token = new URL(caseLink).searchParams.get('t') ?? ''
  const opened = await request.post(`${API}/api/cases/open`, { data: { token } })
  expect(opened.ok(), await opened.text()).toBeTruthy()
  const { session_id: sessionId } = (await opened.json()) as { session_id: string }
  const uploaded = await request.post(`${API}/api/sessions/${sessionId}/documents`, {
    multipart: {
      doc_type: 'sales_data',
      file: { name: file.name, mimeType: file.mimeType ?? 'application/pdf', buffer: file.buffer },
    },
  })
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy()
  const sent = await request.post(`${API}/api/sessions/${sessionId}/chat`, {
    data: { type: 'action', action: 'submit_sales_data', payload: {} },
  })
  expect(sent.ok(), await sent.text()).toBeTruthy()
}

/** Open attention items for a reviewer (GET /api/review/attention). */
export async function attentionFor(
  request: APIRequestContext,
  reviewerId: string,
): Promise<{ trigger: string; reference: string; text: string | null }[]> {
  const res = await request.get(`${API}/api/review/attention`, {
    headers: { 'X-Reviewer-Id': reviewerId },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  const body = (await res.json()) as {
    items: { trigger: string; reference: string; text: string | null }[]
  }
  return body.items
}

/** Advance the simulated clock (runs a proactive tick). */
export async function advanceClock(request: APIRequestContext, hours: number): Promise<void> {
  const res = await request.post(`${API}/api/dev/clock/advance`, { data: { hours } })
  expect(res.ok(), await res.text()).toBeTruthy()
}
