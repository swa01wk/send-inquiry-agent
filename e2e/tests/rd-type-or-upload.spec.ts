import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { readDoneEventCount } from '../support/events'
import { afterTurnChecks } from '../support/turnChecks'
import { draftFields, fieldDisplay, fieldSource } from '../support/draft'
import { fetchDevOutbox, smsOtpCode } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import { reviewerFor } from '../support/submit'

// Demo feedback §3.7 (D11, D12). One scripted model step per model call, in the order of the
// turns below: backend/tests/scenarios/catalogue/rd-type-or-upload*.yaml lists them.

const APPLICANT_EMAIL = 'sara@beanstreet.example'
const APPLICANT_MOBILE = '+966501234567'
// Upload path: no brand name (the Brand Profile gives it); the Arabic name is required and
// isn't in the profile.
const UPLOAD_BUNDLE =
  'Specialty coffee kiosk at Riyadh Mall A, Arabic brand name بين ستريت. Sara Ali, sara@beanstreet.example, 0501234567'
const TYPED_BUNDLE =
  'Bean Street (بين ستريت), a specialty coffee kiosk at Riyadh Mall A. Sara Ali, sara@beanstreet.example, 0501234567'

async function answerCrNo(inquiry: InquiryPage) {
  await expect(inquiry.cards('cr_question')).toBeVisible({ timeout: 60_000 })
  const doneBefore = await readDoneEventCount(inquiry.page)
  await inquiry
    .cards('cr_question')
    .getByRole('button', { name: /no, we don't/i })
    .click()
  await inquiry.waitForTurnDone(doneBefore)
  await afterTurnChecks(inquiry)
}

async function verifyBoth(inquiry: InquiryPage, request: Parameters<typeof fetchDevOutbox>[0]) {
  await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
  await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
  await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))
  await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
}

/** A profile that fills or disagrees starts its own turn (documents_updated {doc_type});
 * wait for it so the next step sees that turn's cards and reply. */
async function uploadProfile(inquiry: InquiryPage, docLabel: string, fileName: string) {
  const doneBefore = await readDoneEventCount(inquiry.page)
  await inquiry.upload(docLabel, fileName)
  await inquiry.waitForTurnDone(doneBefore)
}

function confirmed(draft: Record<string, unknown>, key: string): boolean | undefined {
  return draftFields(draft).find((f) => f.key === key)?.confirmed
}

/** Upload path up to the review card (shared by the first and third tests). */
async function uploadPathToReview(
  inquiry: InquiryPage,
  request: Parameters<typeof fetchDevOutbox>[0],
) {
  await answerCrNo(inquiry)
  await inquiry.say("I'll upload the profiles")
  await afterTurnChecks(inquiry)
  await inquiry.say(UPLOAD_BUNDLE)
  await afterTurnChecks(inquiry)
  await inquiry.confirmCard() // unit type (derived from the message)
  await verifyBoth(inquiry, request)

  await uploadProfile(inquiry, 'Company Profile', 'company_profile_match.pdf')
  await expect(inquiry.page.getByTestId('doc-filled-company_profile')).toContainText('Company name')
  const companyCard = inquiry.page.getByTestId(/confirm-fields-/).last()
  await expect(companyCard).toContainText('Bean Street Trading Co.')
  await expect(companyCard).toContainText(/from: Company Profile, company_profile_match\.pdf/i)
  await inquiry.confirmCard()

  await uploadProfile(inquiry, 'Brand Profile', 'brand_profile_match.pdf')
  await expect(inquiry.page.getByTestId('doc-filled-brand_profile')).toContainText('Brand name')
  await inquiry.confirmCard() // brand name and category; the guard then shows the review card
  await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
}

test.describe('Story rd-type-or-upload @scripted', () => {
  test('upload path fills profiles, shows evidence, and does not re-ask', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload')
    await uploadPathToReview(inquiry, request)

    const draft = await inquiry.draft()
    expect(fieldSource(draft, 'company_name')).toBe('derived')
    expect(fieldSource(draft, 'brand_name_en')).toBe('derived')
    expect(fieldDisplay(draft, 'company_name')).toMatch(/Bean Street Trading/i)
    expect(confirmed(draft, 'company_name')).toBe(true)
    const replies = (await inquiry.allReplies()).join('\n').toLowerCase()
    expect(replies).not.toMatch(/what is your (registered )?company/)

    await inquiry.acceptAndSubmit()
    await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
  })

  test('typed company with profile mismatch warns, keeps value, and flags the brief', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload-typed')
    await answerCrNo(inquiry)
    await inquiry.say("I'll type them")
    await inquiry.say('My Coffee Shop LLC, Olaya Street, Riyadh')
    await afterTurnChecks(inquiry)
    await inquiry.say(TYPED_BUNDLE)
    await afterTurnChecks(inquiry)
    await inquiry.confirmCard() // unit type and category
    await verifyBoth(inquiry, request)

    await uploadProfile(inquiry, 'Company Profile', 'company_profile_mismatch.pdf')
    const warning = (await inquiry.lastReply()).toLowerCase()
    expect(warning).toMatch(/company name|different|profile/)
    expect(warning).not.toMatch(/block|can't submit|cannot submit/)
    await inquiry.say('Keep mine')
    let draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toBe('My Coffee Shop LLC')
    expect(fieldSource(draft, 'company_name')).toBe('user')

    // Everything on the Brand Profile was typed already: nothing to fill, no confirm card.
    await inquiry.upload('Brand Profile', 'brand_profile_match.pdf')
    await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
    draft = await inquiry.draft()
    expect(fieldSource(draft, 'brand_name_en')).toBe('user')
    await inquiry.acceptAndSubmit()
    const reference = await inquiry.successReference()

    const leaseAdmin = await reviewerFor(request, reference, 'first')
    const reviewerPage = await page.context().browser()!.newPage()
    await openCaseAs(reviewerPage, leaseAdmin, reference)
    await expect(reviewerPage.getByTestId('document-check-company_name')).toBeVisible({
      timeout: 30_000,
    })
    await expect(reviewerPage.getByTestId('document-check-company_name')).toContainText(
      'My Coffee Shop LLC',
    )
    await reviewerPage.close()
  })

  test('re-upload after confirm sets values unconfirmed and blocks submit', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload-reupload')
    await uploadPathToReview(inquiry, request)
    expect(confirmed(await inquiry.draft(), 'company_name')).toBe(true)

    const row = inquiry.cards('document_upload').getByTestId('doc-row-company_profile')
    await row.getByRole('button', { name: 'Remove' }).click()
    await expect(row.getByTestId('doc-status')).toHaveText('Not uploaded')
    await uploadProfile(inquiry, 'Company Profile', 'company_profile_match.pdf')

    // ADR-R4: the values came back from the new file and need confirming again.
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toMatch(/Bean Street Trading/i)
    expect(confirmed(draft, 'company_name')).toBe(false)
    expect(draft.can_submit).toBe(false)
    // The new card for the same fields updates the company card in place (chatStore
    // mergeOverlappingConfirmCard): it asks for confirmation again.
    const companyCard = inquiry.page
      .getByTestId(/confirm-fields-/)
      .filter({ hasText: 'Bean Street Trading Co.' })
    await expect(companyCard).toHaveCount(1)
    await expect(companyCard.getByRole('button', { name: 'Looks right' })).toBeEnabled()
  })
})
