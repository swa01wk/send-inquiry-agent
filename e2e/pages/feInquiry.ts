import { expect, type Locator, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  clearCapturedEvents,
  clearFeMockRequests,
  readCapturedEvents,
  readDoneEventCount,
  readFeMockRequests,
  type CapturedSseEvent,
} from '../support/events'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const feFixtures = path.join(__dirname, '../fixtures/files')

export class FeInquiryPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async openMock(scenario?: string) {
    const query = scenario ? `?scenario=${encodeURIComponent(scenario)}` : '/'
    const url = scenario ? query : '/'
    await this.page.goto(url)
    await this.waitForChatReady()
  }

  async waitForChatReady() {
    await expect(this.page.getByRole('region', { name: /leasing assistant chat/i })).toBeVisible({
      timeout: 60_000,
    })
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await expect(box).toBeEnabled({ timeout: 60_000 })
    await clearCapturedEvents(this.page)
    await clearFeMockRequests(this.page)
  }

  async say(text: string) {
    const box = this.page.getByRole('textbox', { name: 'Message' })
    const doneBefore = await readDoneEventCount(this.page)
    await box.fill(text)
    await box.press('Enter')
    await this.waitForTurnDone(doneBefore)
  }

  /** Sends a message without waiting for `done` (stream error / disconnect scenarios). */
  async sendMessageNoWait(text: string) {
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await box.fill(text)
    await box.press('Enter')
  }

  async waitForTurnDone(doneBefore: number) {
    await expect
      .poll(() => readDoneEventCount(this.page), {
        timeout: 60_000,
        message: 'SSE done event after turn',
      })
      .toBeGreaterThan(doneBefore)
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await expect(box).toBeEnabled({ timeout: 60_000 })
  }

  cards(cardType: string): Locator {
    if (cardType === 'confirm_fields') {
      return this.page.locator('[data-testid^="confirm-fields-"]')
    }
    if (cardType === 'document_upload') {
      return this.page.getByTestId('document-checklist-card')
    }
    if (cardType === 'mall_picker') return this.page.getByTestId('mall-picker-card')
    if (cardType === 'verification') return this.page.getByTestId('verification-card')
    if (cardType === 'review') return this.page.getByTestId('review-card')
    if (cardType === 'success') return this.page.getByTestId('success-card')
    if (cardType === 'basic_info_review') return this.page.getByTestId('basic-info-review-card')
    if (cardType === 'send_link') return this.page.getByTestId('send-link-card')
    if (cardType === 'existing_cr_choice') return this.page.getByTestId('existing-cr-choice-card')
    if (cardType === 'sign_in_prompt') return this.page.getByTestId('sign-in-prompt-card')
    return this.page.locator(`[data-testid="card-slot-"]`)
  }

  async lastBotText(): Promise<string> {
    const bubble = this.page.getByTestId('bot-bubble-text').last()
    await expect(bubble).toBeVisible({ timeout: 30_000 })
    return (await bubble.textContent()) ?? ''
  }

  async events(): Promise<CapturedSseEvent[]> {
    return readCapturedEvents(this.page)
  }

  async mockRequests(): Promise<unknown[]> {
    return readFeMockRequests(this.page)
  }

  async confirmCard() {
    const doneBefore = await readDoneEventCount(this.page)
    await this.page.getByRole('button', { name: 'Looks right' }).last().click()
    await this.waitForTurnDone(doneBefore)
  }

  async pickMalls(names: string[]) {
    for (const name of names) {
      await this.page.getByRole('button', { name, exact: true }).click()
    }
    const doneBefore = await readDoneEventCount(this.page)
    await this.page.getByRole('button', { name: 'Done' }).click()
    await this.waitForTurnDone(doneBefore)
  }

  async tapChip(label: string) {
    const doneBefore = await readDoneEventCount(this.page)
    await this.page.getByRole('button', { name: label }).click()
    await this.waitForTurnDone(doneBefore)
  }

  async clickRetry() {
    await this.page.getByRole('button', { name: 'Retry' }).click()
  }
}
