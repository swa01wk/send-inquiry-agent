import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Verification card @fe', () => {
  test('demo email link sends verify_email', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('verification')
    const card = inquiry.cards('verification')
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: /open verification link/i }).click()
    await inquiry.waitForTurnDone(0)
    const requests = await inquiry.mockRequests()
    expect(requests.some((r) => (r as { action?: string }).action === 'verify_email')).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
