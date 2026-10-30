import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Draft panel @fe', () => {
  test('shows progress and field rows', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('draft-panel')
    await expect(page.getByTestId('draft-progress-count')).toBeVisible()
    await expect(page.getByTestId('draft-row-company_name')).toBeVisible()
    await expect(page.getByTestId('draft-row-brand_name_en')).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
