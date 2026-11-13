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
    expect(
      requests.some((r) => (r as { action?: string }).action === 'proceed_basic_info'),
    ).toBeTruthy()
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

  test('contact_check', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('contact-check')
    const card = inquiry.cards('contact_check')
    await expect(card).toBeVisible()
    await card.getByLabel("Caller's email").fill('layla.hassan@oasiscoffee.example')
    await card.getByRole('button', { name: 'Check contact' }).click()
    await inquiry.waitForTurnDone(0)
    expect(
      (await inquiry.mockRequests()).some(
        (r) =>
          (r as { action?: string }).action === 'contact_check' &&
          (r as { payload?: { email?: string } }).payload?.email ===
            'layla.hassan@oasiscoffee.example',
      ),
    ).toBeTruthy()
    await expect(inquiry.cards('inform_tenant')).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('inform_tenant', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('inform-tenant')
    const card = inquiry.cards('inform_tenant')
    await expect(card).toBeVisible()
    await card.getByRole('button', { name: 'Email sign-in link' }).click()
    await inquiry.waitForTurnDone(0)
    expect(
      (await inquiry.mockRequests()).some(
        (r) => (r as { action?: string }).action === 'send_sign_in_link',
      ),
    ).toBeTruthy()
    await expect(card.getByText(/Sign-in link sent to/)).toBeVisible()
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
