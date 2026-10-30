import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Keyboard happy path @fe', () => {
  test('demo flow to confirm card without mouse', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name === 'mobile', 'keyboard path is desktop-only')
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('demo')
    const box = page.getByRole('textbox', { name: 'Message' })
    await box.focus()
    await box.fill('1010123456')
    await box.press('Enter')
    await expect(inquiry.cards('confirm_fields')).toBeVisible({ timeout: 60_000 })
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
