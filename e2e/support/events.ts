/**
 * Playwright helpers for captured SSE (`window.__e2eEvents`) and dev REST endpoints
 * used by INT and FE suites.
 */
import type { APIRequestContext, Page } from '@playwright/test'

export const E2E_API_BASE = process.env.E2E_API_BASE ?? 'http://127.0.0.1:8000'

export type CapturedSseEvent = { event: string; data: Record<string, unknown> }

export type DevOutboxRow = {
  id: string
  template: string
  to: string
  body: string
  links: string[]
}

export type DevAuditEvent = {
  seq: number
  at: string
  type: string
  actor: string
  payload: Record<string, unknown>
}

export async function readCapturedEvents(page: Page): Promise<CapturedSseEvent[]> {
  return page.evaluate(() => {
    const w = window as Window & { __e2eEvents?: CapturedSseEvent[] }
    return w.__e2eEvents ?? []
  })
}

export async function clearCapturedEvents(page: Page): Promise<void> {
  await page.evaluate(() => {
    const w = window as Window & { __e2eEvents?: CapturedSseEvent[] }
    w.__e2eEvents = []
  })
}

export function countRetractions(events: CapturedSseEvent[]): number {
  return events.filter((e) => e.event === 'message_remove').length
}

export function countDoneEvents(events: CapturedSseEvent[]): number {
  return events.filter((e) => e.event === 'done').length
}

export async function readDoneEventCount(page: Page): Promise<number> {
  return countDoneEvents(await readCapturedEvents(page))
}

export async function readFeMockRequests(page: Page): Promise<unknown[]> {
  return page.evaluate(() => {
    const w = window as Window & { __feMockRequests?: unknown[] }
    return w.__feMockRequests ?? []
  })
}

export async function clearFeMockRequests(page: Page): Promise<void> {
  await page.evaluate(() => {
    const w = window as Window & { __feMockRequests?: unknown[] }
    w.__feMockRequests = []
  })
}

export async function clearDevOutbox(request: APIRequestContext): Promise<void> {
  await request.delete(`${E2E_API_BASE}/api/dev/outbox`)
}

export async function fetchDevOutbox(
  request: APIRequestContext,
  to?: string,
): Promise<DevOutboxRow[]> {
  const url = new URL(`${E2E_API_BASE}/api/dev/outbox`)
  if (to) url.searchParams.set('to', to)
  const res = await request.get(url.toString())
  if (!res.ok()) throw new Error(`outbox fetch failed: ${res.status()}`)
  const body = (await res.json()) as { messages: DevOutboxRow[] }
  return body.messages
}

export async function fetchDevAudit(
  request: APIRequestContext,
  inquiryId: string,
): Promise<DevAuditEvent[]> {
  const res = await request.get(`${E2E_API_BASE}/api/dev/audit/${inquiryId}`)
  if (!res.ok()) throw new Error(`audit fetch failed: ${res.status()}`)
  const body = (await res.json()) as { events: DevAuditEvent[] }
  return body.events
}
