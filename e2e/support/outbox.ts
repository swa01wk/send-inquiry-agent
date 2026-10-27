import type { APIRequestContext } from '@playwright/test'

const API = 'http://127.0.0.1:8000'

export interface OutboxRow {
  id: string
  template: string
  to: string
  body: string
  links: string[]
}

export async function clearDevOutbox(request: APIRequestContext): Promise<void> {
  await request.delete(`${API}/api/dev/outbox`)
}

export async function fetchDevOutbox(
  request: APIRequestContext,
  to?: string,
): Promise<OutboxRow[]> {
  const url = new URL(`${API}/api/dev/outbox`)
  if (to) url.searchParams.set('to', to)
  const res = await request.get(url.toString())
  if (!res.ok()) throw new Error(`outbox fetch failed: ${res.status()}`)
  const body = (await res.json()) as { messages: OutboxRow[] }
  return body.messages
}

export function latestByTemplate(messages: OutboxRow[], template: string): OutboxRow | undefined {
  return messages.find((m) => m.template === template)
}
