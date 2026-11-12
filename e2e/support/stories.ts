import { expect, type APIRequestContext, type Browser, type Page } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { A2_CALL_CENTRE_TURNS, C1_EXISTING_CR_TURN } from './channelScripts'
import type { DemoBeat } from './demoPace'
import { fieldDisplay, fieldSource } from './draft'
import {
  clearDevOutbox,
  completeVerifyLink,
  fetchDevOutbox,
  latestByTemplate,
  withE2eScenario,
} from './outbox'
import {
  APPLICANT_EMAIL,
  APPLICANT_MOBILE,
  approveDocumentsViaApi,
  approveLeadViaApi,
  completeApplicationLinkFlow,
  reviewerFor,
  submitScriptedInquiry,
  type ContactOutbox,
} from './submit'

export { A2_CALL_CENTRE_TURNS, C1_EXISTING_CR_TURN }

export const OASIS_APPLICANT_EMAIL = 'layla.hassan@oasiscoffee.example'
export const OASIS_APPLICANT_MOBILE = '+966551110001'

/** Mock sign-in as call-centre or Guest Service staff and open a blank assisted chat. */
export async function openCallCentreChat(
  page: Page,
  staffName: string,
  scenario: string,
): Promise<InquiryPage> {
  await page.goto('/dev')
  await page
    .getByTestId('dev-staff')
    .getByRole('link', { name: new RegExp(staffName) })
    .click()
  await expect(page.getByTestId('callcentre-signed-in')).toBeVisible()

  await page.goto(`/callcentre?e2eScenario=${encodeURIComponent(scenario)}`)
  await expect(page.getByTestId('callcentre-new-inquiry')).toBeVisible()
  await page.getByTestId('callcentre-new-inquiry').click()
  await expect(page.getByRole('region', { name: /leasing assistant chat/i })).toBeVisible({
    timeout: 60_000,
  })

  const staffChat = new InquiryPage(page)
  await staffChat.waitForChatReady()
  return staffChat
}

/** A2 scripted staff turns through to the send-link card. */
export async function startCallCentreInquiry(
  page: Page,
  staffName: string,
  scenario: string,
): Promise<InquiryPage> {
  const staffChat = await openCallCentreChat(page, staffName, scenario)
  for (const turn of A2_CALL_CENTRE_TURNS) {
    await staffChat.say(turn)
  }
  return staffChat
}

export async function staffSendApplicationLink(
  staffChat: InquiryPage,
  request: APIRequestContext,
  applicantEmail: string = APPLICANT_EMAIL,
  applicantScenario = 'a2-applicant',
  beat?: DemoBeat,
): Promise<string> {
  await expect(staffChat.cards('send_link')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(staffChat.page)
  await staffChat.sendApplicationLink()
  await expect(staffChat.cards('send_link').getByText(/Link sent to/i)).toBeVisible()
  if (beat) await beat(staffChat.page)

  await expect
    .poll(async () =>
      latestByTemplate(await fetchDevOutbox(request, applicantEmail), 'complete_application'),
    )
    .toBeTruthy()

  return withE2eScenario(
    completeVerifyLink(await fetchDevOutbox(request, applicantEmail)),
    applicantScenario,
  )
}

/** Applicant completes from the emailed verify link; returns the inquiry reference. */
export async function completeApplicationFromLink(
  browser: Browser,
  request: APIRequestContext,
  verifyPath: string,
  viewportPage: Page,
  contact: ContactOutbox = {
    email: APPLICANT_EMAIL,
    mobile: APPLICANT_MOBILE,
  },
  onApplicantReady?: (page: Page) => Promise<void>,
  beat?: DemoBeat,
): Promise<string> {
  const viewport = viewportPage.viewportSize()
  const applicantContext = await browser.newContext(viewport ? { viewport } : {})
  try {
    const applicantPage = await applicantContext.newPage()
    const applicant = new InquiryPage(applicantPage)
    await applicant.openApplicationVerifyLink(verifyPath)
    if (onApplicantReady) await onApplicantReady(applicantPage)
    return await completeApplicationLinkFlow(applicant, request, contact, beat)
  } finally {
    await applicantContext.close()
  }
}

export async function signInReviewer(
  page: Page,
  reviewer: { id: string; name: string },
): Promise<void> {
  await page.goto('/review')
  await page.getByLabel('Reviewer').selectOption(reviewer.id)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByTestId('signed-in-reviewer')).toContainText(reviewer.name)
}

export async function openReviewerCase(page: Page, reference: string): Promise<void> {
  await page.getByTestId(`queue-row-${reference}`).getByRole('link', { name: reference }).click()
}

/**
 * Open a case signed in as another reviewer (`?as=`, as the "Inquiry for approval" email
 * does): the final reviewer takes over after the Lease Admin's first-level approval.
 */
export async function openCaseAs(
  page: Page,
  reviewer: { id: string; name: string },
  reference: string,
  query = '',
): Promise<void> {
  const extra = query ? `&${query}` : ''
  await page.goto(
    `/review/cases/${encodeURIComponent(reference)}?as=${encodeURIComponent(reviewer.id)}${extra}`,
  )
  await expect(page.getByTestId('case-stage')).toBeVisible()
}

/**
 * R4 (demo feedback §3.8, D13), script rd-signed-in-new-brand: a signed-in Oasis raises on
 * OPP-101. The company comes from the Cenomi record (Yardi) and is confirmed; the new brand is
 * filled from the Brand Profile; the Company Profile disagrees with the record (warned, kept).
 * Returns the reference.
 */
export async function raiseNewBrandFromOpportunities(
  page: Page,
  beat?: DemoBeat,
): Promise<{ inquiry: InquiryPage; reference: string }> {
  // Same origin as the sign-in: the sign-in card's link is absolute (PUBLIC_BASE_URL), and the
  // mock sign-in lives in that origin's sessionStorage.
  const path = '/tenant/opportunities?e2eScenario=rd-signed-in-new-brand'
  await page.goto(page.url().startsWith('http') ? new URL(path, page.url()).toString() : path)
  const opportunity = page.getByTestId('opportunity-OPP-101')
  await expect(opportunity).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel('For brand')).toHaveCount(0)
  if (beat) await beat(page)
  await opportunity.getByRole('button', { name: 'Raise inquiry' }).click()

  const inquiry = new InquiryPage(page)
  await inquiry.waitForChatReady()
  await expect(
    page.getByTestId('bot-bubble-text').filter({ hasText: /from your Cenomi record/ }),
  ).toBeVisible({ timeout: 30_000 })
  await expect(inquiry.cards('basic_info_review')).toContainText('Oasis Coffee Company')
  const draft = await inquiry.draft()
  expect(fieldSource(draft, 'company_name')).toBe('verified')
  expect(fieldDisplay(draft, 'brand_name_en') ?? '').toBeFalsy()
  if (beat) await beat(page)
  await inquiry.proceedBasicInfo()

  await inquiry.say("I'll upload the Brand Profile")
  const documents = inquiry.cards('document_upload')
  await expect(documents).toBeVisible({ timeout: 60_000 })
  await expect(documents.getByTestId('doc-row-company_profile')).toBeVisible()
  await expect(documents.getByTestId('doc-row-brand_profile')).toBeVisible()
  if (beat) await beat(page)

  await inquiry.upload('Brand Profile', 'new_brand_profile.pdf')
  await expect(page.getByTestId(/confirm-fields-/).last()).toContainText('Oasis Bakehouse', {
    timeout: 60_000,
  })
  if (beat) await beat(page)
  await inquiry.confirmCard()
  await inquiry.say('مخبز الواحة')

  await inquiry.upload('Company Profile', 'oasis_company_profile_mismatch.pdf')
  expect((await inquiry.lastReply()).toLowerCase()).toMatch(/cenomi record/)
  if (beat) await beat(page)
  await inquiry.say("Keep the record's name")
  await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
  const reviewed = await inquiry.draft()
  expect(fieldDisplay(reviewed, 'company_name')).toBe('Oasis Coffee Company')
  expect(fieldSource(reviewed, 'brand_name_en')).toBe('derived')
  if (beat) await beat(page)
  await inquiry.acceptAndSubmit()
  const reference = await inquiry.successReference()
  if (beat) await beat(page)
  return { inquiry, reference }
}

/** The new brand as an existing tenant types it (scripts a1-existing-tenant). */
export const NEW_BRAND_TYPED = 'Oasis Bakehouse (مخبز الواحة), a café'

/** Existing tenant: sign in, raise on an opportunity, confirm the company from the Cenomi
 * record, type the new brand, upload both profiles, submit. */
export async function raiseTenantInquiry(
  page: Page,
  tenantName: RegExp | string,
  opportunityId: string,
  scenario: string,
  welcomePattern?: RegExp,
  beat?: DemoBeat,
): Promise<{ inquiry: InquiryPage; reference: string }> {
  await clearDevOutbox(page.request)

  await page.goto('/dev')
  await page.getByTestId('dev-tenants').getByRole('link', { name: tenantName }).click()
  await expect(page.getByTestId('tenant-signed-in')).toBeVisible()

  await page.goto(`/tenant/opportunities?e2eScenario=${encodeURIComponent(scenario)}`)
  await expect(page.getByTestId(`opportunity-${opportunityId}`)).toBeVisible({
    timeout: 30_000,
  })
  await page
    .getByTestId(`opportunity-${opportunityId}`)
    .getByRole('button', { name: 'Raise inquiry' })
    .click()
  await expect(page.getByRole('region', { name: /leasing assistant chat/i })).toBeVisible({
    timeout: 60_000,
  })

  const inquiry = new InquiryPage(page)
  await inquiry.waitForChatReady()
  if (welcomePattern) {
    await expect(
      page.getByTestId('bot-bubble-text').filter({ hasText: welcomePattern }),
    ).toBeVisible({ timeout: 30_000 })
    if (beat) await beat(page)
  }

  await expect(inquiry.cards('basic_info_review')).toBeVisible({
    timeout: 60_000,
  })
  if (beat) await beat(page)
  await inquiry.proceedBasicInfo()
  await expect(
    inquiry.cards('basic_info_review').getByText('Basic information confirmed'),
  ).toBeVisible()
  if (beat) await beat(page)
  // R4 (demo feedback §3.8): every inquiry raised here is a new brand, and both profiles
  // are uploaded afresh (the a1-existing-tenant script types the brand).
  await inquiry.say(NEW_BRAND_TYPED)
  await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.upload('Company Profile', 'company_profile.pdf')
  await inquiry.upload('Brand Profile', 'brand_profile.pdf')
  await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.acceptAndSubmit()
  await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  const reference = await inquiry.successReference()
  return { inquiry, reference }
}

const API = 'http://127.0.0.1:8000'

/** Advance the simulated clock until local time in `timezone` is `targetHour` (0–23). */
export async function advanceClockToLocalHour(
  request: APIRequestContext,
  targetHour: number,
): Promise<void> {
  const clock = (await (await request.get(`${API}/api/dev/clock`)).json()) as {
    now: string
    timezone: string
  }
  const hours = hoursUntilLocalHour(clock.now, clock.timezone, targetHour)
  const res = await request.post(`${API}/api/dev/clock/advance`, {
    data: { hours },
  })
  expect(res.ok()).toBeTruthy()
}

function hoursUntilLocalHour(isoNow: string, timeZone: string, targetHour: number): number {
  const now = new Date(isoNow)
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(now)
  const n = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value ?? 0)
  const h = n('hour')
  const m = n('minute')
  const s = n('second')
  let diffHours = targetHour - h
  if (diffHours <= 0) diffHours += 24
  return diffHours - m / 60 - s / 3600
}

/** Advance the simulated clock from `/dev` (runs proactive tick). */
export async function advanceClockFromDevPage(
  page: Page,
  button: '+24 h' | '+48 h' | 'To morning (08:00)',
): Promise<void> {
  await page.goto('/dev')
  await expect(page.getByTestId('dev-clock')).not.toHaveText('Loading…')
  await page.getByRole('button', { name: button }).click()
  await expect(page.getByTestId('dev-message')).toBeVisible()
}

function outboxRowsForReference(
  messages: Awaited<ReturnType<typeof fetchDevOutbox>>,
  template: string,
  reference: string,
) {
  return messages.filter((m) => m.template === template && m.body.includes(reference))
}

/** L5 beats on a single fresh inquiry (reset first); asserts only on that reference. */
export async function runL5AttentionFlow(
  page: Page,
  request: APIRequestContext,
  beat?: DemoBeat,
): Promise<void> {
  await request.post(`${API}/api/dev/reset`)
  const reference = await submitScriptedInquiry(page, request, 's1-happy-path', beat)
  const reviewer = await reviewerFor(request, reference)

  const emailsForRef = async (template: string) =>
    outboxRowsForReference(await fetchDevOutbox(request), template, reference)

  await advanceClockFromDevPage(page, '+48 h')
  expect(await emailsForRef('review_stalled')).toHaveLength(1)

  await page.goto('/dev')
  await page.getByTestId('dev-reviewers').getByRole('link', { name: reviewer.name }).click()
  await expect(page.getByTestId('attention-badge')).toHaveText('1')
  await page.getByTestId('attention-link').click()
  await expect(page.getByTestId(`attention-stalled_review-${reference}`)).toBeVisible()
  if (beat) await beat(page)

  await advanceClockFromDevPage(page, '+48 h')
  expect(await emailsForRef('review_escalated')).toHaveLength(1)
  await page.goto('/dev')
  const managerId = `${reviewer.id.split('-')[0]}-manager`
  await page.locator(`a[href="/review?as=${managerId}"]`).click()
  await page.getByTestId('attention-link').click()
  await expect(page.getByTestId(`attention-escalation-${reference}`)).toBeVisible()
  if (beat) await beat(page)

  await page.goto(`/review?as=${encodeURIComponent(reviewer.id)}`)
  await page.getByTestId(`queue-row-${reference}`).getByRole('link', { name: reference }).click()
  // Day R2: the Lease Admin approves each document first (demo feedback §3.4).
  await approveDocumentsViaApi(request, reference)
  await page.reload()
  await page.getByRole('button', { name: 'Approve first level' }).click()
  await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
  // Flow v2 (§3.7): the contacts request opens at "Approve Lead?" = Yes.
  await approveLeadViaApi(request, reference)
  if (beat) await beat(page)
  await advanceClockFromDevPage(page, '+48 h')
  await advanceClockFromDevPage(page, '+24 h')
  expect(
    (await fetchDevOutbox(request)).filter((m) => m.template === 'applicant_reminder'),
  ).toHaveLength(0)

  await page.goto(
    `/review/attention?as=${encodeURIComponent(reviewer.id)}&e2eScenario=r2-tenant-reminder`,
  )
  const reminder = page.getByTestId(`attention-applicant_reminder-${reference}`)
  await expect(reminder.getByLabel('Reminder to the applicant')).toHaveValue(/company contacts/)
  if (beat) await beat(page)
  await reminder.getByTestId('attention-draft-assistant').click()
  await expect(reminder.getByTestId('attention-assistant-draft')).toBeVisible({
    timeout: 60_000,
  })
  if (beat) await beat(page)
  await reminder.getByTestId('attention-use-draft').click()
  await expect(reminder.getByLabel('Reminder to the applicant')).toHaveValue(/contacts/)
  if (beat) await beat(page)

  await advanceClockToLocalHour(request, 23)
  await reminder.getByRole('button', { name: 'Approve and send' }).click()
  await expect(reminder.getByTestId('attention-held')).toContainText('held until')
  if (beat) await beat(page)
  expect(
    (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
      (m) => m.template === 'applicant_reminder',
    ),
  ).toHaveLength(0)

  await advanceClockFromDevPage(page, 'To morning (08:00)')
  const sent = (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
    (m) => m.template === 'applicant_reminder',
  )
  expect(sent).toHaveLength(1)
  expect(sent[0].links.some((l) => l.includes('/inquiry/case?t='))).toBe(true)
}

/** Every persona link on `/dev` opens the expected surface in one click. */
export async function assertDevPersonasOpenInOneClick(page: Page): Promise<void> {
  await page.goto('/dev')
  await expect(page.getByTestId('dev-home')).toBeVisible()
  await expect(page.getByTestId('dev-clock')).not.toHaveText('Loading…')

  await page.getByRole('link', { name: /Applicant chat/i }).click()
  await expect(page.getByRole('region', { name: /leasing assistant chat/i })).toBeVisible({
    timeout: 60_000,
  })
  await page.goto('/dev')

  await page.getByRole('link', { name: /Dev inbox/i }).click()
  await expect(page.getByTestId('dev-inbox-page')).toBeVisible()
  await page.goto('/dev')

  await page.getByRole('link', { name: /Needs attention/i }).click()
  await expect(
    page
      .getByTestId('attention-page')
      .or(page.getByRole('link', { name: /Sign in as a reviewer/i })),
  ).toBeVisible({ timeout: 30_000 })
  await page.goto('/dev')

  const staffCount = await page.getByTestId('dev-staff').getByRole('link').count()
  for (let i = 0; i < staffCount; i++) {
    await page.goto('/dev')
    await page.getByTestId('dev-staff').getByRole('link').nth(i).click()
    await expect(page.getByTestId('callcentre-signed-in')).toBeVisible()
  }

  const tenantCount = await page.getByTestId('dev-tenants').getByRole('link').count()
  for (let i = 0; i < tenantCount; i++) {
    await page.goto('/dev')
    await page.getByTestId('dev-tenants').getByRole('link').nth(i).click()
    await expect(page.getByTestId('tenant-signed-in')).toBeVisible()
  }

  const reviewerCount = await page.getByTestId('dev-reviewers').getByRole('link').count()
  for (let i = 0; i < reviewerCount; i++) {
    await page.goto('/dev')
    await page.getByTestId('dev-reviewers').getByRole('link').nth(i).click()
    await expect(page.getByTestId('signed-in-reviewer')).toBeVisible()
  }
}

/** Confirm **Reset demo** on `/dev` and wait for the success message. */
export async function resetDemoFromDevPage(page: Page): Promise<void> {
  await page.goto('/dev')
  await page.getByRole('button', { name: 'Reset demo' }).click()
  await page.getByRole('button', { name: 'Yes, reset everything' }).click()
  await expect(page.getByTestId('dev-message')).toContainText(/reset/i)
}

/** After reset: empty queue, attention, tenant inquiries and dev inbox. */
export async function assertCleanAfterDemoReset(page: Page): Promise<void> {
  await page.goto('/dev/inbox')
  await expect(page.getByText('No messages yet.')).toBeVisible()

  await page.goto('/dev')
  const firstReviewer = page.getByTestId('dev-reviewers').getByRole('link').first()
  await firstReviewer.click()
  await expect(page.getByTestId('queue-empty')).toBeVisible()
  await page.getByTestId('attention-link').click()
  await expect(page.getByTestId('attention-empty')).toBeVisible()

  await page.goto('/dev')
  await page
    .getByTestId('dev-tenants')
    .getByRole('link', { name: /Oasis Coffee Company/ })
    .click()
  await page.goto('/tenant/inquiries')
  await expect(page.getByTestId('my-inquiries-empty')).toBeVisible()
}
