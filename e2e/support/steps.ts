import {
  expect,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Page,
} from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { InquiryPage } from '../pages/inquiry'
import { readDoneEventCount } from './events'
import { fetchDevOutbox, latestByTemplate, withE2eScenario } from './outbox'
import { persona, scriptFor, type CatalogueEntry, type CatalogueStep } from './scenarios'
import { openCallCentreChat } from './stories'
import { approveDocumentsViaApi, reviewerFor } from './submit'
import { reviewerAct } from './flowV2'

/**
 * Flow v2 test plan §6: the catalogue's abstract steps, done in the browser. Each step makes
 * the same calls (and so the same agent turns) as the AGENT-DET / AGENT-LIVE runner
 * (backend/scripts/flow_v2_eval_live.py), so one scripted model serves both layers:
 * confirming a section follows GET /api/dev/confirm-plan, and uploads follow the chat's own
 * rule for when a turn runs.
 */
const API = 'http://127.0.0.1:8000'
const fixtures = path.join(path.dirname(fileURLToPath(import.meta.url)), '../fixtures/files')
const STAFF_NAME = 'Sami Al Anazi'
const DOC_LABELS: Record<string, string> = {
  company_profile: 'Company Profile',
  brand_profile: 'Brand Profile',
}

export interface StepCtx {
  page: Page
  browser: Browser
  request: APIRequestContext
  entry: CatalogueEntry
  /** The chat the next step acts on (the applicant's after the call-centre link). */
  chat: InquiryPage
  /** Scripted (INT) or real model (E2E-LIVE). */
  live: boolean
  staffSessionId?: string
  contexts: BrowserContext[]
}

function script(ctx: StepCtx, suffix = ''): string | undefined {
  return ctx.live ? undefined : `${scriptFor(ctx.entry.id)}${suffix}`
}

/** Opens the entry's first chat: the public page, or the call-centre console for CC1–CC3. */
export async function openEntryChat(
  page: Page,
  browser: Browser,
  request: APIRequestContext,
  entry: CatalogueEntry,
  live: boolean,
): Promise<StepCtx> {
  const ctx: StepCtx = {
    page,
    browser,
    request,
    entry,
    chat: new InquiryPage(page),
    live,
    contexts: [],
  }
  if ((entry.contexts ?? []).includes('call_centre')) {
    ctx.chat = await openCallCentreChat(page, STAFF_NAME, script(ctx) ?? '')
    ctx.staffSessionId = ctx.chat.sessionId ?? undefined
    return ctx
  }
  const faults = (entry.steps ?? []).find((s) => 'mock_faults' in s)?.mock_faults as
    | string
    | undefined
  await ctx.chat.open(script(ctx), faults ? { faults } : {})
  return ctx
}

async function turn(ctx: StepCtx, act: () => Promise<void>): Promise<void> {
  const doneBefore = await readDoneEventCount(ctx.chat.page)
  await act()
  await ctx.chat.waitForTurnDone(doneBefore)
}

async function action(ctx: StepCtx, name: string, payload: Record<string, unknown> = {}) {
  // Only where the browser can't (a resend button still counting down): the same call the
  // card would make, outside the page.
  const res = await ctx.request.post(`${API}/api/sessions/${ctx.chat.sessionId}/chat`, {
    data: { type: 'action', action: name, payload },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
}

async function confirmSection(ctx: StepCtx, section: string): Promise<void> {
  const res = await ctx.request.get(`${API}/api/dev/confirm-plan/${ctx.chat.sessionId}`, {
    params: { section },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  const plan = (await res.json()) as { card_ids: string[]; say_yes: boolean }
  for (const cardId of plan.card_ids) {
    const card = ctx.chat.page.locator(`[data-testid^="confirm-fields-${cardId}"]`).last()
    await turn(ctx, () => card.getByRole('button', { name: 'Looks right' }).click())
  }
  if (plan.say_yes) await ctx.chat.say("Yes, that's all correct.")
}

async function draftChecks(ctx: StepCtx): Promise<Record<string, unknown>> {
  const draft = await ctx.chat.draft()
  return (draft.checks ?? {}) as Record<string, unknown>
}

async function uploadOne(ctx: StepCtx, docType: string, fileName: string): Promise<void> {
  const page = ctx.chat.page
  const card = page.getByTestId('document-checklist-card').last()
  const row = card
    .locator('[data-testid^="doc-row-"]')
    .filter({ hasText: DOC_LABELS[docType] ?? docType })
  const doneBefore = await readDoneEventCount(page)
  const response = page
    .waitForResponse((r) => r.url().includes('/documents') && r.request().method() === 'POST', {
      timeout: 10_000,
    })
    .catch(() => null)
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    row.getByRole('button', { name: /Upload|Replace/i }).click(),
  ])
  if (fileName === 'too_big.pdf') {
    // Over the card's limit without a big file in the repo.
    await chooser.setFiles({
      name: fileName,
      mimeType: 'application/pdf',
      buffer: Buffer.alloc(26 * 1024 * 1024, 0x20),
    })
  } else {
    await chooser.setFiles(path.join(fixtures, fileName))
  }
  const res = await response
  if (!res || !res.ok()) return // refused by the card (type or size): no turn in the app
  const body = (await res.json()) as {
    fields_filled?: string[]
    mismatches?: unknown[]
    draft?: { checks?: { required_docs_uploaded?: number; required_docs_total?: number } }
  }
  const done = body.draft?.checks?.required_docs_uploaded ?? 0
  const total = body.draft?.checks?.required_docs_total ?? 2
  if (
    (body.fields_filled?.length ?? 0) > 0 ||
    (body.mismatches?.length ?? 0) > 0 ||
    done === total
  ) {
    await ctx.chat.waitForTurnDone(doneBefore)
  }
}

async function openApplicationLink(ctx: StepCtx): Promise<void> {
  // The spec clears the outbox first, so the newest application link is this run's.
  const mail = await fetchDevOutbox(ctx.request)
  const link = latestByTemplate(mail, 'complete_application')?.links.find((l) =>
    l.includes('/inquiry/verify'),
  )
  expect(link, 'complete_application email').toBeTruthy()
  const viewport = ctx.page.viewportSize()
  const context = await ctx.browser.newContext(viewport ? { viewport } : {})
  ctx.contexts.push(context)
  const applicant = new InquiryPage(await context.newPage())
  const applicantScript = script(ctx, '-applicant')
  await applicant.openApplicationVerifyLink(
    applicantScript ? withE2eScenario(link!, applicantScript) : link!,
  )
  ctx.chat = applicant
}

async function proceedBasicInfoOnce(ctx: StepCtx): Promise<void> {
  const card = ctx.chat.cards('basic_info_review').last()
  if ((await card.count()) === 0) return
  const proceed = card.getByRole('button', { name: 'Proceed' })
  if ((await proceed.count()) === 0 || !(await proceed.isEnabled())) return
  await turn(ctx, () => proceed.click())
}

export async function runStep(ctx: StepCtx, step: CatalogueStep): Promise<void> {
  const chat = ctx.chat
  if ('mock_faults' in step || step.leave) return
  if (step.cr_skip === true) {
    const card = chat.cards('company_registration').last()
    await turn(ctx, () => card.getByRole('button', { name: /^skip$/i }).click())
    return
  }
  if (step.cr_skip_confirm === true) {
    const card = chat.cards('company_registration').last()
    await turn(ctx, () => card.getByRole('button', { name: /yes, continue without it/i }).click())
    return
  }
  if (typeof step.cr_verify === 'string') return chat.verifyCr(step.cr_verify)
  if (typeof step.say === 'string') return chat.say(step.say)
  if (typeof step.confirm_card === 'string') return confirmSection(ctx, step.confirm_card)
  if (step.verify_email === true) {
    if ((await draftChecks(ctx)).email_verified) return
    const card = chat.cards('verification').last()
    await turn(ctx, () => card.getByRole('button', { name: /open verification link/i }).click())
    return
  }
  if ('enter_code' in step) {
    await proceedBasicInfoOnce(ctx)
    const card = chat.cards('verification').last()
    await card.locator('#otp-code').fill(String(step.enter_code))
    await turn(ctx, () => card.getByRole('button', { name: 'Verify', exact: true }).click())
    return
  }
  if (step.accept_terms === true) {
    // The applicant's link chat (CC2, CC3) accepts the terms on the review card instead.
    if ((await chat.cards('terms').count()) === 0) return
    return chat.acceptTerms()
  }
  if (step.upload && typeof step.upload === 'object') {
    for (const [docType, fileName] of Object.entries(step.upload as Record<string, string>)) {
      await uploadOne(ctx, docType, fileName)
    }
    return
  }
  if (step.submit === true) return chat.acceptAndSubmit()
  if (typeof step.resend_otp_times === 'number') {
    for (let i = 0; i < step.resend_otp_times; i++) await action(ctx, 'resend_otp')
    return
  }
  if (typeof step.dev_clock_advance_minutes === 'number') {
    const res = await ctx.request.post(`${API}/api/dev/clock/advance`, {
      data: { hours: step.dev_clock_advance_minutes / 60 },
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    return
  }
  if (step.new_session === true) return chat.open(script(ctx))
  if (typeof step.tap_chip === 'string') {
    if (/continue/i.test(step.tap_chip)) {
      await chat.page.getByRole('button', { name: /continue my inquiry/i }).click()
      return
    }
    return chat.say(step.tap_chip)
  }
  if (typeof step.resume_pending === 'string') {
    const inline = chat.page.getByTestId('resume-pending-inline')
    if (!(await inline.isVisible())) {
      await chat.page.getByRole('button', { name: /continue my inquiry/i }).click()
    }
    await inline.getByRole('textbox').fill(step.resume_pending)
    await turn(ctx, () => inline.getByRole('button', { name: /^continue$/i }).click())
    return
  }
  if (step.open_resume_link === true) {
    const email = persona('sara').email ?? 'sara@beanstreet.example'
    const link = latestByTemplate(await fetchDevOutbox(ctx.request, email), 'resume_link')?.links[0]
    expect(link, 'resume_link email').toBeTruthy()
    const url = new URL(link!)
    await chat.page.goto(`${url.pathname}${url.search}`)
    await expect(chat.page.getByTestId('verify-page')).toBeVisible({ timeout: 30_000 })
    await chat.page.getByRole('button', { name: /continue your inquiry/i }).click()
    await chat.waitForChatReady()
    return
  }
  if (Array.isArray(step.pick_malls)) return chat.pickMalls(step.pick_malls as string[])
  if (step.reviewer === 'approve_documents_and_first_level') {
    const reference = await chat.successReference()
    await approveDocumentsViaApi(ctx.request, reference)
    const first = await reviewerFor(ctx.request, reference, 'first')
    await reviewerAct(ctx.request, first.id, reference, 'approve_first')
    return
  }
  if (step.seed_open_inquiry && typeof step.seed_open_inquiry === 'object') {
    const spec = step.seed_open_inquiry as { cr_number: string; mall: string }
    const res = await ctx.request.post(`${API}/api/dev/flow/seed`, {
      data: { stage: 'submitted', malls: [spec.mall], cr_number: spec.cr_number },
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    return
  }
  // Call centre (CC1–CC3): the executive's chat, then the applicant's.
  if (typeof step.cc_cr === 'string') return chat.say(`The caller's CR number is ${step.cc_cr}.`)
  if (typeof step.cc_contact_check === 'string') {
    const card = chat.cards('contact_check').last()
    await card.getByLabel("Caller's email").fill(step.cc_contact_check)
    await turn(ctx, () => card.getByRole('button', { name: 'Check contact' }).click())
    return
  }
  if (step.cc_send_sign_in_link === true) {
    const card = chat.cards('inform_tenant').last()
    await turn(ctx, () => card.getByRole('button', { name: 'Email sign-in link' }).click())
    return
  }
  if (typeof step.cc_capture === 'string') {
    for (const section of step.cc_capture.split(',')) {
      await chat.say(ctx.entry.cc_dictation?.[section] ?? '')
      await confirmSection(ctx, section)
    }
    return
  }
  if (step.cc_submit === true) {
    const button = chat.cards('send_link').last().getByRole('button', {
      name: 'Send application link',
    })
    if ((await button.count()) === 0 || !(await button.isEnabled())) {
      await chat.say("That's everything from the caller — please show the application link.")
    }
    return chat.sendApplicationLink()
  }
  if (step.open_application_link === true) return openApplicationLink(ctx)
  if (Array.isArray(step.edit_field)) {
    const [field, value] = step.edit_field as [string, string]
    const words: Record<string, string> = { last_name: 'last name', first_name: 'first name' }
    return chat.say(`One correction: my ${words[field] ?? field} is ${value}.`)
  }
  throw new Error(`unsupported catalogue step: ${JSON.stringify(step)}`)
}
