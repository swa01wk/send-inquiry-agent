import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { countRetractions, readDoneEventCount } from '../../support/events'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Stream edge cases @fe', () => {
  test('error event with Retry', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('stream-error-retry')
    await inquiry.sendMessageNoWait('trigger error')
    await expect(page.getByText(/Mock stream failed/i)).toBeVisible()
    const doneBefore = await readDoneEventCount(page)
    await inquiry.clickRetry()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(page.getByTestId('bot-bubble-text').filter({ hasText: 'Back online' })).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('message_remove retracts bot text', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('stream-message-remove')
    await inquiry.sendMessageNoWait('hello')
    await expect(page.getByTestId('bot-bubble-text').filter({ hasText: 'corrected reply' })).toBeVisible({
      timeout: 30_000,
    })
    expect(countRetractions(await inquiry.events())).toBeGreaterThan(0)
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('409 turn_in_progress then Retry', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('stream-turn-in-progress')
    await inquiry.sendMessageNoWait('hello')
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
    const doneBefore = await readDoneEventCount(page)
    await inquiry.clickRetry()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(page.getByTestId('bot-bubble-text').filter({ hasText: 'Ready when you are' })).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })

  test('dropped connection with Retry', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('stream-dropped-connection')
    await inquiry.sendMessageNoWait('hello')
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
    const doneBefore = await readDoneEventCount(page)
    await inquiry.clickRetry()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(
      page.getByTestId('bot-bubble-text').filter({ hasText: 'Connection restored' }),
    ).toBeVisible()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})
