/**
 * Helpers for the live re-demo flows (`rd-live-flows.spec.ts`): per-turn checks that run on
 * the real model's output, and leak checks on the page itself.
 *
 * Checks that judge the model's behaviour are soft (`softly`): a run reports every deviation
 * in a flow instead of stopping at the first, and still fails at the end. Steps the flow
 * can't continue without stay hard expectations in the spec.
 */
import { expect, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'
import type { InquiryPage } from '../pages/inquiry'
import { readCapturedEvents, readDoneEventCount } from './events'
import { assertSafetyInvariants, sliceEventsAfterDone } from './invariants'

export const API = 'http://127.0.0.1:8000'

export const hasLlmCredentials = () =>
  Boolean(process.env.OPENAI_API_KEY || process.env.AZURE_OPENAI_API_KEY)

/** Runs `fn`; a failure is recorded as a soft failure named `label`, and the flow goes on. */
export async function softly(label: string, fn: () => unknown | Promise<unknown>): Promise<void> {
  try {
    await fn()
  } catch (error) {
    const first = String((error as Error).message ?? error).split('\n').find((l) => l.trim())
    expect.soft(false, `${label} — ${first ?? 'failed'}`).toBe(true)
  }
}

// Internal words that must never reach an applicant, reviewer or call-centre agent.
const REPLY_LEAKS: [RegExp, string][] = [
  [/ui_event/i, 'a ui_event note'],
  [/\[guard/i, 'a guard note'],
  [
    /\b(update_draft|verify_cr|confirm_fields|send_verification|request_documents|show_review|suggest_replies|show_mall_picker|get_master_data|show_application_link|search_faq|get_inquiry_status|start_follow_on)\b/,
    'a tool name',
  ],
  [
    /\b(still_needed|verification_complete|documents_complete|basic_info_confirmed|cards_shown|card_id|tool_calls?|retry_agent)\b/,
    'an internal note or state key',
  ],
  [/\bundefined\b|\bNaN\b|\[object Object\]/, 'a JavaScript value'],
  [/[{}]/, 'JSON braces'],
  [/\b(riyadh|jeddah|dammam)-[a-z0-9-]+\b|\bfnb_[a-z_]+\b/, 'a master-data id'],
  [/\b(system prompt|my instructions|as an ai language model)\b/i, 'prompt talk'],
]

/** Emails and file names may contain underscores; anything else snake_case is jargon. */
const SNAKE = /\b[a-z]+_[a-z0-9_]+\b/

export function replyLeaks(reply: string): string[] {
  const found = REPLY_LEAKS.filter(([re]) => re.test(reply)).map(([, label]) => label)
  const scrubbed = reply
    .replace(/\S+@\S+/g, ' ')
    .replace(/\b[\w.-]+\.(pdf|png|jpe?g|docx?|xlsx?|zip|txt)\b/gi, ' ')
  if (SNAKE.test(scrubbed)) found.push(`snake_case (${scrubbed.match(SNAKE)![0]})`)
  return found
}

// Raw values that mean a template or component rendered something it shouldn't.
const PAGE_LEAKS =
  /\[ui_event\]|\[guard|\bundefined\b|\bNaN\b|\[object Object\]|"card_type"|"payload"|\bnull\b/

/** The visible text of `page` carries no raw values or internal notes. */
export async function assertNoPageLeaks(page: Page, label: string): Promise<void> {
  await softly(`${label}: page shows no raw values or internal notes`, async () => {
    const text = await page.locator('body').innerText()
    const match = text.match(PAGE_LEAKS)
    expect(match?.[0] ?? null, `leaked "${match?.[0]}"`).toBeNull()
  })
}

/** Collects uncaught page errors; check with `assertNoPageErrors`. */
export function watchPageErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  return errors
}

export async function assertNoPageErrors(errors: string[], label: string): Promise<void> {
  await softly(`${label}: no uncaught errors in the page`, () => expect(errors).toEqual([]))
}

async function draftOrEmpty(
  request: APIRequestContext,
  sessionId: string | null,
): Promise<Record<string, unknown>> {
  if (!sessionId) return {}
  const res = await request.get(`${API}/api/sessions/${sessionId}/draft`)
  return res.ok() ? ((await res.json()) as Record<string, unknown>) : {}
}

/**
 * A chat driven against the live model. Every turn (a message or a card action) is followed
 * by soft checks: at most one retracted reply, no internal wording in the reply, and the
 * safety invariants I1–I8 on what the turn did.
 */
const openChats: LiveChat[] = []

/**
 * On failure, attach each chat's replies and draft fields (who said what, and what the draft
 * held), then forget the chats. Call from `test.afterEach`.
 */
export async function attachLiveTranscripts(testInfo: TestInfo): Promise<void> {
  const chats = openChats.splice(0)
  if (testInfo.status === testInfo.expectedStatus) return
  for (const chat of chats) {
    // The turn log survives the page: case chats and reviewer contexts close before this runs.
    let draftText = '(page closed)'
    if (!chat.page.isClosed()) {
      const draft = await draftOrEmpty(chat.page.request, chat.inquiry.sessionId)
      type Field = { key: string; display: string | null; source: string | null; confirmed: boolean }
      draftText = ((draft.fields ?? []) as Field[])
        .filter((f) => f.display)
        .map((f) => `${f.key} = ${f.display} (${f.source}${f.confirmed ? ', confirmed' : ''})`)
        .join('\n')
    }
    await testInfo.attach(`${chat.name} turns.txt`, {
      body: `${chat.log.join('\n\n')}\n\n--- draft ---\n${draftText}`,
      contentType: 'text/plain',
    })
  }
}

/** Soft check on the newest reply; the failure shows the reply. */
export async function replyCheck(
  chat: LiveChat,
  label: string,
  pattern: RegExp,
  expected: 'matches' | 'does not match' = 'matches',
): Promise<void> {
  const reply = await chat.lastReply()
  await softly(`${chat.name}: ${label}`, () => {
    const ok = pattern.test(reply) === (expected === 'matches')
    expect(ok, `reply ${expected} ${pattern}: "${reply.slice(0, 300)}"`).toBe(true)
  })
}

export class LiveChat {
  constructor(
    readonly inquiry: InquiryPage,
    /** Public self-service chat (I8: no CR number or registry details anywhere). */
    readonly publicCr: boolean,
    readonly name: string,
  ) {
    openChats.push(this)
  }

  /** One entry per turn: what was done, the tools the agent called, and its reply. */
  readonly log: string[] = []
  private auditSeen = new Map<string, number>()

  /** Tools the agent called since the last look (audit `tool_called`), for the turn log. */
  private async toolsSinceLastTurn(): Promise<string[]> {
    const sessionId = this.inquiry.sessionId
    if (!sessionId) return []
    const res = await this.page.request.get(`${API}/api/dev/audit/${sessionId}`).catch(() => null)
    if (!res?.ok()) return []
    const events = ((await res.json()) as {
      events: { seq: number; type: string; payload: Record<string, unknown> }[]
    }).events
    const seen = this.auditSeen.get(sessionId) ?? 0
    this.auditSeen.set(sessionId, Math.max(seen, ...events.map((e) => e.seq)))
    return events
      .filter((e) => e.seq > seen && e.type === 'tool_called' && e.payload.layer === 'agent')
      .map((e) => `${e.payload.name}${e.payload.outcome && e.payload.outcome !== 'ok' ? ` (${e.payload.outcome})` : ''}`)
  }

  get page(): Page {
    return this.inquiry.page
  }

  async turn(label: string, act: () => Promise<void>): Promise<void> {
    const request = this.page.request
    const doneBefore = await readDoneEventCount(this.page)
    const draftBefore = await draftOrEmpty(request, this.inquiry.sessionId)
    await act()
    const events = sliceEventsAfterDone(await readCapturedEvents(this.page), doneBefore)
    const where = `${this.name} · ${label}`

    await softly(`${where}: at most one retracted reply`, () =>
      expect(events.filter((e) => e.event === 'message_remove').length).toBeLessThanOrEqual(1),
    )
    const replies = await this.inquiry.allReplies().catch(() => [] as string[])
    const reply = replies[replies.length - 1] ?? ''
    const tools = await this.toolsSinceLastTurn()
    const retracted = events.filter((e) => e.event === 'message_remove').length
    this.log.push(
      `> ${label}\n  tools: ${tools.join(', ') || '—'}${retracted ? `\n  retracted replies: ${retracted}` : ''}\n  reply: ${reply}`,
    )
    await softly(`${where}: reply has no internal wording`, () =>
      expect(replyLeaks(reply), reply).toEqual([]),
    )
    if (this.inquiry.sessionId) {
      const draftAfter = await draftOrEmpty(request, this.inquiry.sessionId)
      await softly(`${where}: safety invariants`, () =>
        assertSafetyInvariants(
          request,
          this.inquiry.sessionId!,
          events,
          draftBefore,
          draftAfter,
          { publicCrQuestion: this.publicCr },
        ),
      )
    }
  }

  say(text: string): Promise<void> {
    return this.turn(`"${text}"`, () => this.inquiry.say(text))
  }

  /** Every bot reply so far, lower-cased and joined (for "never said X" checks). */
  async transcript(): Promise<string> {
    return (await this.inquiry.allReplies()).join('\n').toLowerCase()
  }

  async lastReply(): Promise<string> {
    return (await this.inquiry.lastReply()).toLowerCase()
  }
}
