import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { readDoneEventCount } from '../../support/events'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Choice card @fe', () => {
  test('a tap sends choose_option and closes the card (18 Nov B1)', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('choice')
    const card = page.getByTestId('choice-card-sales_category')
    await expect(card).toBeVisible()
    await expect(card.locator('[data-testid^="choice-option-"]')).toHaveCount(2)
    const doneBefore = await readDoneEventCount(page)
    await card.getByTestId('choice-option-fnb_cafe').click()
    await inquiry.waitForTurnDone(doneBefore)
    const requests = (await inquiry.mockRequests()) as {
      action?: string
      payload?: Record<string, unknown>
    }[]
    expect(requests.find((r) => r.action === 'choose_option')?.payload).toEqual({
      card_id: 'choice-sales_category',
      key: 'sales_category',
      value: 'fnb_cafe',
    })
    await expect(card.getByTestId('choice-option-fnb_cafe')).toHaveAttribute('aria-pressed', 'true')
    await expect(card.getByTestId('choice-option-fnb_restaurant')).toBeDisabled()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
