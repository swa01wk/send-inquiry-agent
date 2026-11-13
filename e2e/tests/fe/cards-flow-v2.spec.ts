import { expect, test } from '@playwright/test'
import { readDoneEventCount } from '../../support/events'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Flow v2 cards @fe', () => {
  test('company registration verify and skip confirm', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('company-registration')

    await page.getByPlaceholder('10-digit CR number').fill('1010123456')
    const doneBefore = await readDoneEventCount(page)
    await page.getByRole('button', { name: 'Verify' }).click()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(page.getByTestId('cr-masked')).toContainText('•••••• 3456')

    const doneSkip = await readDoneEventCount(page)
    await page.getByRole('button', { name: 'Skip' }).click()
    await inquiry.waitForTurnDone(doneSkip)
    await expect(page.getByTestId('skip-confirm')).toBeVisible()
    await expect(
      page.getByText('Are you sure you want to proceed without CR ID?'),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /yes, continue without it/i }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: /no, i'll enter it/i })).toBeVisible()

    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('terms card accepts on checkbox', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('terms-card')
    const doneBefore = await readDoneEventCount(page)
    await page.getByRole('checkbox').check()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(page.getByTestId('terms-accepted')).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
