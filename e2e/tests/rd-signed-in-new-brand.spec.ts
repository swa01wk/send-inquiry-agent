import { expect, test } from '@playwright/test'
import { openCaseAs, raiseNewBrandFromOpportunities } from '../support/stories'
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
    const { reference } = await raiseNewBrandFromOpportunities(page)

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
