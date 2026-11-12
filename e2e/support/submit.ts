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
 * `s1-happy-path`) to a submitted inquiry, without per-turn checks. Returns the reference.
 * `files` picks the profile fixtures: the mock document review reads the expiry from the
 * file name (`company_expired.pdf`, `brand_soon.pdf`; demo feedback §3.3). */
export async function submitScriptedInquiry(
  page: Page,
  request: APIRequestContext,
  scenario: string,
  beat?: (page: Page) => Promise<void>,
  files: { company?: string; brand?: string } = {},
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
  await inquiry.upload('Company Profile', files.company ?? 'company_profile.pdf')
  await inquiry.upload('Brand Profile', files.brand ?? 'brand_profile.pdf')
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

type DecisionDetail = {
  brief: {
    documents: {
      doc_type: string
      uploaded: boolean
      file_id: string | null
      approval?: string | null
      expiry_tracked?: boolean
      expiry_status?: string | null
    }[]
    contacts: { role: string; contact_id?: string | null; approval?: string }[]
  }
}

async function caseDetailAs(
  request: APIRequestContext,
  reviewerId: string,
  reference: string,
): Promise<DecisionDetail> {
  const res = await request.get(`${API}/api/review/cases/${encodeURIComponent(reference)}`, {
    headers: { 'X-Reviewer-Id': reviewerId },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as DecisionDetail
}

async function actAs(
  request: APIRequestContext,
  reviewerId: string,
  reference: string,
  action: string,
  payload: Record<string, unknown>,
): Promise<void> {
  const res = await request.post(
    `${API}/api/review/cases/${encodeURIComponent(reference)}/actions`,
    { headers: { 'X-Reviewer-Id': reviewerId }, data: { action, payload } },
  )
  expect(res.ok(), await res.text()).toBeTruthy()
}

/** A date a year from today, `YYYY-MM-DD`. */
function aYearAhead(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() + 1)
  return date.toISOString().slice(0, 10)
}

/**
 * Day R2 (demo feedback §3.4): the Lease Admin approves every pending document through the
 * console API, confirming an expiry date first where none is known (documents on file, or
 * the review service didn't answer). Stories that aren't about document approval call this
 * before **Approve first level**, then reload the console.
 */
export async function approveDocumentsViaApi(
  request: APIRequestContext,
  reference: string,
): Promise<void> {
  const leaseAdmin = await reviewerFor(request, reference, 'first')
  const detail = await caseDetailAs(request, leaseAdmin.id, reference)
  for (const doc of detail.brief.documents) {
    if (!doc.uploaded || !doc.file_id || doc.approval !== 'pending') continue
    const ids = { doc_type: doc.doc_type, file_id: doc.file_id }
    if (doc.expiry_tracked && doc.expiry_status === 'unknown') {
      await actAs(request, leaseAdmin.id, reference, 'confirm_document_expiry', {
        ...ids,
        expiry_date: aYearAhead(),
      })
    }
    await actAs(request, leaseAdmin.id, reference, 'approve_document', ids)
  }
}

/**
 * Day R2 (demo feedback §3.5): the Lease Admin approves every pending tenant contact through
 * the console API. Stories that aren't about contact approval call this before the final
 * **Approve**, then reload the console.
 */
export async function approveContactsViaApi(
  request: APIRequestContext,
  reference: string,
): Promise<void> {
  const leaseAdmin = await reviewerFor(request, reference, 'first')
  const detail = await caseDetailAs(request, leaseAdmin.id, reference)
  for (const contact of detail.brief.contacts) {
    if (contact.approval !== 'pending' || !contact.contact_id) continue
    await actAs(request, leaseAdmin.id, reference, 'approve_contact', {
      contact_id: contact.contact_id,
    })
  }
}

/**
 * Flow v2 day F2 (spec §3.7): the final reviewer assigns a unit on the inquiry's first mall
 * and answers "Approve Lead?" = Yes, which opens the contacts request. Stories that aren't
 * about the second level call this after **Approve first level**, before the contacts.
 */
export async function approveLeadViaApi(
  request: APIRequestContext,
  reference: string,
  unit: { unit_ref?: string; area_sqm?: number } = {},
): Promise<void> {
  const reviewer = await reviewerFor(request, reference, 'final')
  const res = await request.get(`${API}/api/review/cases/${encodeURIComponent(reference)}`, {
    headers: { 'X-Reviewer-Id': reviewer.id },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  const detail = (await res.json()) as { inquiry_malls?: { id: string }[] }
  const mall = detail.inquiry_malls?.[0]?.id
  expect(mall, 'the inquiry has a mall').toBeTruthy()
  await actAs(request, reviewer.id, reference, 'assign_unit', {
    mall_id: mall,
    unit_ref: unit.unit_ref ?? 'G-014',
    area_sqm: unit.area_sqm ?? 95,
  })
  await actAs(request, reviewer.id, reference, 'approve_lead', {})
}
