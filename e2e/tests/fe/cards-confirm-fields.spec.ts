import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Confirm fields card @fe', () => {
  test('renders and sends confirm_card on Looks right', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('confirm-fields')
    const card = inquiry.cards('confirm_fields')
    await expect(card).toBeVisible()
    await expect(card.getByText('Bean Street Trading Co.')).toBeVisible()
    await inquiry.confirmCard()
    const requests = await inquiry.mockRequests()
    expect(requests.some((r) => (r as { action?: string }).action === 'confirm_card')).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
