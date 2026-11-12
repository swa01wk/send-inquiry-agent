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
