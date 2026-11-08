import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { afterTurnChecks } from '../support/turnChecks'
import { fieldDisplay, fieldSource } from '../support/draft'
import { fetchDevOutbox, smsOtpCode } from '../support/outbox'
import { openCaseAs, reviewerFor } from '../support/stories'

const APPLICANT_EMAIL = 'sara@beanstreet.example'
const APPLICANT_MOBILE = '+966501234567'
const BRAND_BUNDLE =
  'Bean Street specialty coffee kiosk at Riyadh Mall A. Sara Ali, sara@beanstreet.example, 0501234567'

test.describe('Story rd-type-or-upload @scripted', () => {
  test('upload path fills profiles, shows evidence, and does not re-ask', async ({ page, request }) => {
    test.setTimeout(360_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload')
    await expect(inquiry.cards('cr_question')).toBeVisible({ timeout: 60_000 })
    await inquiry
      .cards('cr_question')
      .getByRole('button', { name: /no, we don't/i })
      .click()
    await afterTurnChecks(inquiry)
    await inquiry.tapChip("I'll upload the profiles")
    await afterTurnChecks(inquiry)
    await inquiry.say(BRAND_BUNDLE)
    await afterTurnChecks(inquiry)
    await inquiry.confirmCard()

    await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
    await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
    await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))

    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.upload('Company Profile', 'company_profile_match.pdf')
    await expect(inquiry.page.getByTestId('doc-filled-company_profile')).toContainText(
      'Company name',
    )
    const confirmCo = inquiry.page.getByTestId(/confirm-fields-/)
    await expect(confirmCo).toContainText('Bean Street Trading Co.')
    await expect(confirmCo).toContainText(/from: Company Profile, company_profile_match\.pdf/i)
    await inquiry.confirmCard()

    await inquiry.upload('Brand Profile', 'brand_profile_match.pdf')
    await expect(inquiry.page.getByTestId('doc-filled-brand_profile')).toContainText('Brand name')
    await inquiry.confirmCard()

    const draft = await inquiry.draft()
    expect(fieldSource(draft, 'company_name')).toBe('derived')
    expect(fieldSource(draft, 'brand_name_en')).toBe('derived')
    expect(fieldDisplay(draft, 'company_name')).toMatch(/Bean Street Trading/i)

    await expect(inquiry.cards('review')).toBeVisible({ timeout: 90_000 })
    const reply = await inquiry.lastReply()
    expect(reply.toLowerCase()).not.toMatch(/what is your (registered )?company/)

    await inquiry.acceptAndSubmit()
    await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
  })

  test('typed company with profile mismatch warns, keeps value, and flags the brief', async ({
    page,
    request,
  }) => {
    test.setTimeout(360_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload-typed')
    await expect(inquiry.cards('cr_question')).toBeVisible({ timeout: 60_000 })
    await inquiry
      .cards('cr_question')
      .getByRole('button', { name: /no, we don't/i })
      .click()
    await afterTurnChecks(inquiry)
    await inquiry.tapChip("I'll type them")
    await inquiry.say('My Coffee Shop LLC, Olaya Street, Riyadh')
    await afterTurnChecks(inquiry)
    await inquiry.say(BRAND_BUNDLE)
    await afterTurnChecks(inquiry)
    await inquiry.confirmCard()

    await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
    await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
    await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))

    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.upload('Company Profile', 'company_profile_mismatch.pdf')
    const warning = await inquiry.lastReply()
    expect(warning.toLowerCase()).toMatch(/company name|different|profile/)
    await inquiry.say('Keep my company name')
    await inquiry.upload('Brand Profile', 'brand_profile_match.pdf')
    await inquiry.confirmCard()

    await expect(inquiry.cards('review')).toBeVisible({ timeout: 90_000 })
    await inquiry.acceptAndSubmit()
    const reference = await inquiry.successReference()

    const leaseAdmin = await reviewerFor(request, reference, 'first')
    const reviewerPage = await page.context().browser()!.newPage()
    await openCaseAs(reviewerPage, leaseAdmin, reference)
    await expect(reviewerPage.getByTestId('document-check-company_name')).toBeVisible({
      timeout: 30_000,
    })
    await reviewerPage.close()
  })

  test('re-upload after confirm sets values unconfirmed and blocks submit', async ({
    page,
    request,
  }) => {
    test.setTimeout(360_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-type-or-upload')
    await inquiry
      .cards('cr_question')
      .getByRole('button', { name: /no, we don't/i })
      .click()
    await inquiry.tapChip("I'll upload the profiles")
    await inquiry.say(BRAND_BUNDLE)
    await inquiry.confirmCard()
    await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
    await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
    await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))
    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.upload('Company Profile', 'company_profile_match.pdf')
    await inquiry.confirmCard()
    await inquiry.upload('Brand Profile', 'brand_profile_match.pdf')
    await inquiry.confirmCard()
    await expect(inquiry.cards('review')).toBeVisible({ timeout: 90_000 })

    const row = inquiry.cards('document_upload').getByTestId('doc-row-company_profile')
    await row.getByRole('button', { name: 'Remove' }).click()
    await inquiry.upload('Company Profile', 'company_profile_match.pdf')
    await expect(inquiry.page.getByRole('button', { name: 'Looks right' }).last()).toBeVisible({
      timeout: 60_000,
    })
    const review = inquiry.cards('review')
    await expect(review.getByRole('button', { name: 'Submit inquiry' })).toBeDisabled()
  })
})
