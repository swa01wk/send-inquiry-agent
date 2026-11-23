import type { APIRequestContext } from '@playwright/test'

const API = 'http://127.0.0.1:8000'

export interface OutboxRow {
  id: string
  template: string
  to: string
  subject?: string
  /** The case reference (or session) the message belongs to. */
  inquiry_id?: string
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

/** Four-digit OTP from the newest `sms_otp` row (mock SMS body). */
export function smsOtpCode(messages: OutboxRow[]): string {
  const sms = latestByTemplate(messages, 'sms_otp')
  const code = sms?.body.match(/\b(\d{4})\b/)?.[1]
  if (!code) throw new Error('sms_otp code not in outbox')
  return code
}

/** Case reference from the newest global `review_assigned` email. */
export function referenceFromReviewAssigned(messages: OutboxRow[]): string {
  const assigned = latestByTemplate(messages, 'review_assigned')
  const consoleLink = assigned?.links.find((l) => l.includes('/review/cases/'))
  if (!consoleLink) throw new Error('review_assigned console link missing')
  return decodeURIComponent(consoleLink.split('/review/cases/')[1].split('?')[0])
}

/** `/inquiry/verify` URL from the newest `complete_application` email. */
export function completeVerifyLink(messages: OutboxRow[]): string {
  const mail = latestByTemplate(messages, 'complete_application')
  const link = mail?.links.find((l) => l.includes('/inquiry/verify'))
  if (!link) throw new Error('complete_application verify link missing')
  return link
}

/**
 * Token of the newest email-verification link sent for a chat (template
 * `email_verification_link`). The verification card never carries the link (18 Nov B1, N7,
 * ADR-N3), so tests open it from the outbox, as the applicant opens it from their email.
 */
export function emailLinkToken(messages: OutboxRow[], sessionId: string): string {
  for (const m of messages) {
    if (m.template !== 'email_verification_link') continue
    if (m.inquiry_id && m.inquiry_id !== sessionId) continue
    for (const link of m.links) {
      const token = new URL(link, 'http://127.0.0.1:5173').searchParams.get('t')
      if (token) return token
    }
  }
  throw new Error(`email verification link not in outbox for ${sessionId}`)
}

/**
 * Opens the chat's email link from the outbox (18 Nov B1). The open chat gets the same
 * `verify_email` event as before (one agent turn when it completes verification, quiet while
 * the mobile code is still pending), sent outside the page: the link is opened elsewhere.
 */
export async function openEmailLink(request: APIRequestContext, sessionId: string): Promise<void> {
  const token = emailLinkToken(await fetchDevOutbox(request), sessionId)
  const res = await request.post(`${API}/api/sessions/${sessionId}/chat`, {
    data: { type: 'action', action: 'verify_email', payload: { token } },
  })
  if (!res.ok()) throw new Error(`verify_email failed: ${res.status()} ${await res.text()}`)
}

/** Append or replace `e2eScenario` for scripted verify/resume (Playwright `baseURL` paths). */
export function withE2eScenario(link: string, scenario: string): string {
  const u = link.startsWith('http') ? new URL(link) : new URL(link, 'http://127.0.0.1:5173')
  u.searchParams.set('e2eScenario', scenario)
  return `${u.pathname}${u.search}`
}
