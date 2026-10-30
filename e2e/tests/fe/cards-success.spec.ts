import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Success card @fe', () => {
  test('shows reference and tracking link', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('success')
    const card = inquiry.cards('success')
    await expect(card).toBeVisible()
    await expect(card).toContainText('GEO-SPC-482917')
    await expect(card.getByRole('link', { name: 'Track your inquiry' })).toHaveAttribute(
      'href',
      /482917/,
    )
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
