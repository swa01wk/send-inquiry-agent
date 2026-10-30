import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Intake channel cards @fe', () => {
  test('basic_info_review proceed', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('basic-info-review')
    await expect(inquiry.cards('basic_info_review')).toBeVisible()
    await expect(page.getByText(/Started by the Cenomi call centre/i)).toBeVisible()
    const doneBefore = 0
    await page.getByRole('button', { name: 'Proceed' }).click()
    await inquiry.waitForTurnDone(doneBefore)
    const requests = await inquiry.mockRequests()
    expect(requests.some((r) => (r as { action?: string }).action === 'proceed_basic_info')).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('send_link card', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('send-link')
    const card = inquiry.cards('send_link')
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: /send application link/i }).click()
    await inquiry.waitForTurnDone(0)
    expect(
      (await inquiry.mockRequests()).some(
        (r) => (r as { action?: string }).action === 'send_application_link',
      ),
    ).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('existing_cr_choice', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('existing-cr-choice')
    await expect(inquiry.cards('existing_cr_choice')).toBeVisible()
    await page.getByRole('button', { name: /continue as a new inquiry/i }).click()
    await inquiry.waitForTurnDone(0)
    expect(
      (await inquiry.mockRequests()).some(
        (r) => (r as { action?: string }).action === 'existing_cr_choice',
      ),
    ).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('sign_in_prompt', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('sign-in-prompt')
    const card = inquiry.cards('sign_in_prompt')
    await expect(card).toBeVisible()
    await expect(card.getByRole('link', { name: 'Sign in to Tenant Central' })).toHaveAttribute(
      'href',
      '/tenant',
    )
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
