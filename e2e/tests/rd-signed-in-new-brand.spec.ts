import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fieldDisplay, fieldSource } from '../support/draft'
import { openCaseAs } from '../support/stories'
import { reviewerFor } from '../support/submit'

/**
 * Re-demo story rd-signed-in-new-brand (demo feedback §3.8, D13): Oasis, signed in, raises on
 * OPP-101. The company comes from Yardi by CR and is confirmed; the new brand is filled from
 * the Brand Profile; both profiles are uploaded; a Company Profile that disagrees with the
 * Cenomi record warns, never blocks, and is flagged for the Lease Admin.
 */
test.describe('Story rd-signed-in-new-brand @scripted', () => {
  test('company from Yardi, brand from the Brand Profile, profile check in the brief', async ({
    page,
    browser,
  }) => {
    test.setTimeout(240_000)
    await page.goto('/dev')
    await page
      .getByTestId('dev-tenants')
      .getByRole('link', { name: /Oasis Coffee Company/ })
      .click()
    await expect(page.getByTestId('tenant-signed-in')).toBeVisible()
    await page.goto('/tenant/opportunities?e2eScenario=rd-signed-in-new-brand')
    const opportunity = page.getByTestId('opportunity-OPP-101')
    await expect(opportunity).toBeVisible({ timeout: 30_000 })
    await expect(page.getByLabel('For brand')).toHaveCount(0)
    await opportunity.getByRole('button', { name: 'Raise inquiry' }).click()

    const inquiry = new InquiryPage(page)
    await inquiry.waitForChatReady()
    await expect(
      page.getByTestId('bot-bubble-text').filter({ hasText: /from your Cenomi record/ }),
    ).toBeVisible({ timeout: 30_000 })
    const basicInfo = inquiry.cards('basic_info_review')
    await expect(basicInfo).toContainText('Oasis Coffee Company')
    let draft = await inquiry.draft()
    expect(fieldSource(draft, 'company_name')).toBe('verified')
    expect(fieldDisplay(draft, 'brand_name_en') ?? '').toBeFalsy()
    await inquiry.proceedBasicInfo()

    await inquiry.say("I'll upload the Brand Profile")
    const documents = inquiry.cards('document_upload')
    await expect(documents).toBeVisible({ timeout: 60_000 })
    await expect(documents.getByTestId('doc-row-company_profile')).toBeVisible()
    await expect(documents.getByTestId('doc-row-brand_profile')).toBeVisible()

    await inquiry.upload('Brand Profile', 'new_brand_profile.pdf')
    const confirm = page.getByTestId(/confirm-fields-/).last()
    await expect(confirm).toContainText('Oasis Bakehouse', { timeout: 60_000 })
    await inquiry.confirmCard()
    await inquiry.say('مخبز الواحة')

    await inquiry.upload('Company Profile', 'oasis_company_profile_mismatch.pdf')
    expect((await inquiry.lastReply()).toLowerCase()).toMatch(/cenomi record/)
    await inquiry.say("Keep the record's name")
    await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })

    draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toBe('Oasis Coffee Company')
    expect(fieldSource(draft, 'brand_name_en')).toBe('derived')
    await inquiry.acceptAndSubmit()
    const reference = await inquiry.successReference()

    const leaseAdmin = await reviewerFor(page.request, reference, 'first')
    const reviewerContext = await browser.newContext()
    try {
      const reviewerPage = await reviewerContext.newPage()
      await openCaseAs(reviewerPage, leaseAdmin, reference)
      await expect(reviewerPage.getByTestId('document-check-company_name')).toBeVisible({
        timeout: 30_000,
      })
    } finally {
      await reviewerContext.close()
    }
  })
})
