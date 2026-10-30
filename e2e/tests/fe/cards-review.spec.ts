import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Review card @fe', () => {
  test('terms gate blocks submit until checked', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('review')
    const review = inquiry.cards('review')
    await expect(review).toBeVisible()
    const submit = review.getByRole('button', { name: 'Submit inquiry' })
    await expect(submit).toBeDisabled()
    await review.getByRole('checkbox').check()
    await expect(submit).toBeEnabled()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
