import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Confirm fields card @fe', () => {
  test('confirms one row with its value button (18 Nov B1, M27)', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('confirm-fields')
    const card = inquiry.cards('confirm_fields')
    await expect(card).toBeVisible()
    await expect(page.getByRole('button', { name: 'Looks right' })).toHaveCount(0)
    await expect(card.getByTestId('confirm-field-company_name')).toContainText(
      'Bean Street Trading Co.',
    )
    await expect(card.getByTestId('edit-field-company_name')).toBeVisible()
    await inquiry.confirmField()
    const requests = (await inquiry.mockRequests()) as {
      action?: string
      payload?: { card_id?: string; key?: string }
    }[]
    const sent = requests.find((r) => r.action === 'confirm_field')
    expect(sent?.payload).toEqual({ card_id: 'confirm-1', key: 'company_name' })
    // The card comes back with that row ticked; the other row still has its button.
    await expect(card.getByTestId('confirm-field-company_name')).toHaveCount(0)
    await expect(card.getByTestId('confirm-field-company_address')).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
