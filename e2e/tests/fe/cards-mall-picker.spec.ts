import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Mall picker card @fe', () => {
  test('select_malls payload', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('mall-picker')
    await expect(inquiry.cards('mall_picker')).toBeVisible()
    await inquiry.pickMalls(['Riyadh Mall A'])
    const requests = await inquiry.mockRequests()
    const select = requests.find(
      (r) => (r as { type?: string; action?: string }).action === 'select_malls',
    ) as { payload?: { mall_ids?: string[] } } | undefined
    expect(select?.payload?.mall_ids).toContain('riyadh-mall-a')
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
