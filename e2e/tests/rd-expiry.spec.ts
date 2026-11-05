import { expect, test } from '@playwright/test'
import { clearDevOutbox } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import { reviewerFor, submitScriptedInquiry } from '../support/submit'

/** `YYYY-MM-DD` a year from today. */
function aYearAhead(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() + 1)
  return date.toISOString().slice(0, 10)
}

/**
 * Re-demo story rd-expiry (demo feedback §3.4, D6): the mock document review reads the
 * expiry from the file name. An expired profile has Reject preselected and Approve disabled;
 * one expiring soon can be approved; a corrected date updates the status.
 */
test.describe('Story rd-expiry @scripted', () => {
  test('expired, expiring soon, and a corrected date', async ({ page, request }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path', undefined, {
      company: 'company_expired.pdf',
      brand: 'brand_soon.pdf',
    })
    const leaseAdmin = await reviewerFor(request, reference, 'first')
    await openCaseAs(page, leaseAdmin, reference)

    const companyStatus = page.getByTestId('doc-expiry-status-company_profile')
    await expect(companyStatus).toContainText('Expired on')
    await expect(page.getByTestId('doc-approve-company_profile')).toBeDisabled()
    const companyRow = page.getByTestId('doc-row-company_profile')
    await expect(companyRow.getByLabel('Remarks (needed to reject)')).toHaveValue(
      /^This document expired on .+\. Please upload a current one\.$/,
    )
    await expect(page.getByTestId('doc-reject-company_profile')).toBeEnabled()

    await expect(page.getByTestId('doc-expiry-status-brand_profile')).toContainText('Expiring soon')
    await page.getByTestId('doc-approve-brand_profile').click()
    await expect(page.getByTestId('doc-approval-brand_profile')).toHaveText('Approved')

    // The Lease Admin corrects the company profile's date (e.g. read from the document).
    await page.getByTestId('doc-expiry-company_profile').fill(aYearAhead())
    await companyRow.getByRole('button', { name: 'Save date' }).click()
    await expect(companyStatus).toContainText('Valid until')
    await expect(page.getByTestId('doc-approve-company_profile')).toBeEnabled()
    await page.getByTestId('doc-approve-company_profile').click()
    await expect(page.getByTestId('first-approval-blockers')).toHaveCount(0)
    await expect(
      page.getByTestId('action-approve_first').getByRole('button', { name: 'Approve first level' }),
    ).toBeEnabled()
  })
})
