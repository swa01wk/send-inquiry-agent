import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Verification card @fe', () => {
  test('has no link button; the link is opened from the email (18 Nov B1, N7)', async ({
    page,
  }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('verification')
    const card = inquiry.cards('verification')
    await expect(card).toBeVisible()
    await expect(card.getByRole('button', { name: /open verification link/i })).toHaveCount(0)
    await expect(card).toContainText('Open it from your email')
    await expect(card.getByRole('button', { name: /resend link/i })).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
