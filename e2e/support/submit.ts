import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fetchDevOutbox, latestByTemplate, referenceFromReviewAssigned, smsOtpCode } from './outbox'

const API = 'http://127.0.0.1:8000'

async function ensureDocumentReady(inquiry: InquiryPage, docLabel: string, fileName: string) {
  const card = inquiry.cards('document_upload')
  const row = card.locator('[data-testid^="doc-row-"]').filter({ hasText: docLabel })
  await expect(row).toHaveCount(1)
  const status = row.getByTestId('doc-status')
  const text = ((await status.textContent()) ?? '').trim()
  if (text === 'On file' || text.startsWith('Uploaded')) return
  await inquiry.upload(docLabel, fileName)
}

export const APPLICANT_EMAIL = 'sara@beanstreet.example'
export const APPLICANT_MOBILE = '+966501234567'

export type ContactOutbox = { email: string; mobile: string }

/** The S1 scripted path (`scenario` must be a script in `backend/tests/e2e_scripts/`, e.g.
 * `s1-happy-path`) to a submitted inquiry, without per-turn checks. Returns the reference. */
export async function submitScriptedInquiry(
  page: Page,
  request: APIRequestContext,
  scenario: string,
  beat?: (page: Page) => Promise<void>,
): Promise<string> {
  const inquiry = new InquiryPage(page)
  await inquiry.open(scenario)
  await inquiry.say('1010123456')
  if (beat) await beat(page)
  await inquiry.confirmCard()
  if (beat) await beat(page)
  await inquiry.say(
    'Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567',
  )
  if (beat) await beat(page)
  await inquiry.confirmCard()
  if (beat) await beat(page)
  await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
  await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))
  if (beat) await beat(page)
  await expect(inquiry.cards('document_upload')).toBeVisible({
    timeout: 90_000,
  })
  if (beat) await beat(page)
  await inquiry.upload('Company Profile', 'company_profile.pdf')
  await inquiry.upload('Brand Profile', 'brand_profile.pdf')
  await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.acceptAndSubmit()
  await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)

  return referenceFromReviewAssigned(await fetchDevOutbox(request))
}

/** Applicant path after opening the call-centre `complete_application` link (scripted `a2-applicant`). */
export async function completeApplicationLinkFlow(
  inquiry: InquiryPage,
  request: APIRequestContext,
  contact: ContactOutbox = {
    email: APPLICANT_EMAIL,
    mobile: APPLICANT_MOBILE,
  },
  beat?: (page: Page) => Promise<void>,
): Promise<string> {
  const page = inquiry.page
  await expect(inquiry.cards('basic_info_review')).toBeVisible({
    timeout: 60_000,
  })
  if (beat) await beat(page)
  await inquiry.proceedBasicInfo()
  await expect(
    inquiry.cards('basic_info_review').getByText('Basic information confirmed'),
  ).toBeVisible()
  if (beat) await beat(page)
  await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, contact.mobile)))
  if (beat) await beat(page)
  await expect(inquiry.cards('document_upload')).toBeVisible({
    timeout: 90_000,
  })
  if (beat) await beat(page)
  await ensureDocumentReady(inquiry, 'Company Profile', 'company_profile.pdf')
  await ensureDocumentReady(inquiry, 'Brand Profile', 'brand_profile.pdf')
  await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  await inquiry.acceptAndSubmit()
  await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
  if (beat) await beat(page)
  return inquiry.successReference()
}

/**
 * The reviewer who acts on `reference` at `level` (demo feedback §3.2): the Lease Admin of
 * the mall's region for the first level, the RLM / RPLM of the product line for the final
 * level. Both see the case in their queue.
 */
export async function reviewerFor(
  request: APIRequestContext,
  reference: string,
  level: 'first' | 'final' = 'first',
): Promise<{ id: string; name: string; role: string }> {
  const reviewers = (await (await request.get(`${API}/api/review/reviewers`)).json()) as {
    id: string
    name: string
    role: string
    manager: boolean
  }[]
  const holders: { id: string; name: string; role: string }[] = []
  for (const reviewer of reviewers.filter((r) => !r.manager)) {
    const res = await request.get(`${API}/api/review/cases`, {
      headers: { 'X-Reviewer-Id': reviewer.id },
    })
    const cases = (await res.json()) as { reference: string }[]
    if (cases.some((c) => c.reference === reference)) holders.push(reviewer)
  }
  const wanted = holders.find((r) =>
    level === 'first' ? r.role === 'lease_admin' : r.role !== 'lease_admin',
  )
  const reviewer = wanted ?? holders[0]
  if (!reviewer) throw new Error(`No reviewer has ${reference} in their queue`)
  return reviewer
}
