import { expect, type Locator, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  clearCapturedEvents,
  readCapturedEvents,
  readDoneEventCount,
  type CapturedSseEvent,
} from '../support/events'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const fixtures = path.join(__dirname, '../fixtures/files')

export class InquiryPage {
  readonly page: Page
  sessionId: string | null = null
  private userSoFar = ''

  constructor(page: Page) {
    this.page = page
  }

  async open(scenario?: string) {
    if (scenario) {
      await this.page.route('**/api/sessions', async (route) => {
        if (route.request().method() !== 'POST') {
          await route.continue()
          return
        }
        const headers = {
          ...route.request().headers(),
          'X-Test-Scenario': scenario,
        }
        await route.continue({ headers })
      })
    }
    const sessionIds: string[] = []
    const onResponse = async (response: { url: () => string; request: () => { method: () => string }; ok: () => boolean; json: () => Promise<unknown> }) => {
      if (!response.url().includes('/api/sessions') || response.request().method() !== 'POST' || !response.ok()) {
        return
      }
      const body = (await response.json()) as { session_id: string }
      sessionIds.push(body.session_id)
    }
    this.page.on('response', onResponse)
    const url = scenario ? `/?e2eScenario=${encodeURIComponent(scenario)}` : '/'
    await this.page.goto(url)
    await expect
      .poll(() => sessionIds.length, { timeout: 120_000, message: 'session create response' })
      .toBeGreaterThan(0)
    await expect
      .poll(
        () =>
          this.page.evaluate(() => {
            const w = window as Window & { __e2eSessionId?: string }
            return w.__e2eSessionId ?? null
          }),
        { timeout: 120_000, message: 'frontend session ready' },
      )
      .toBeTruthy()
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await expect(box).toBeEnabled({ timeout: 120_000 })
    this.page.off('response', onResponse)
    this.sessionId = sessionIds[sessionIds.length - 1] ?? null
    const fromWindow = await this.page.evaluate(() => {
      const w = window as Window & { __e2eSessionId?: string }
      return w.__e2eSessionId ?? null
    })
    if (fromWindow) this.sessionId = fromWindow
    await clearCapturedEvents(this.page)
  }

  async say(text: string) {
    this.userSoFar += `\n${text}`
    const box = this.page.getByRole('textbox', { name: 'Message' })
    const doneBefore = await readDoneEventCount(this.page)
    await box.fill(text)
    await box.press('Enter')
    await this.waitForTurnDone(doneBefore)
  }

  async waitForTurnDone(doneBefore: number) {
    await expect
      .poll(() => readDoneEventCount(this.page), {
        timeout: 120_000,
        message: 'SSE done event after turn',
      })
      .toBe(doneBefore + 1)
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await expect(box).toBeEnabled({ timeout: 120_000 })
  }

  async tapChip(label: string) {
    await this.page.getByRole('button', { name: label }).click()
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

  /** Stands in for clicking the emailed link (the card's demo button, EMAIL_LINK_DEMO). */
  async verifyEmail() {
    const card = this.cards('verification')
    const doneBefore = await readDoneEventCount(this.page)
    await card.getByRole('button', { name: /open verification link/i }).click()
    await this.waitForTurnDone(doneBefore)
  }

  async enterCode(code: string) {
    const card = this.cards('verification')
    await card.locator('#otp-code').fill(code)
    const doneBefore = await readDoneEventCount(this.page)
    await card.getByRole('button', { name: 'Verify', exact: true }).click()
    await this.waitForTurnDone(doneBefore)
  }

  async pickFile(docLabel: string, fileName: string) {
    const card = this.page.getByTestId('document-checklist-card')
    const row = card.locator('div').filter({ hasText: docLabel }).first()
    const [chooser] = await Promise.all([
      this.page.waitForEvent('filechooser'),
      row.getByRole('button', { name: 'Upload' }).click(),
    ])
    await chooser.setFiles(path.join(fixtures, fileName))
  }

  async upload(docLabel: string, fileName: string) {
    const doneBefore = await readDoneEventCount(this.page)
    await this.pickFile(docLabel, fileName)
    const card = this.page.getByTestId('document-checklist-card')
    const row = card.locator('div').filter({ hasText: docLabel }).first()
    await expect(row.getByText(/Uploaded/i)).toBeVisible({ timeout: 30_000 })
    const header = card.getByText(/\d+ of \d+ required uploaded/)
    const headerText = (await header.textContent()) ?? ''
    const match = headerText.match(/(\d+) of (\d+) required uploaded/)
    if (match && match[1] === match[2]) {
      await this.waitForTurnDone(doneBefore)
    }
  }

  async expectUploadError(docLabel: string, message: string) {
    const card = this.page.getByTestId('document-checklist-card')
    const row = card.locator('div').filter({ hasText: docLabel }).first()
    await expect(row.getByText(message)).toBeVisible()
  }

  async acceptAndSubmit() {
    const review = this.cards('review')
    await expect(review).toBeVisible({ timeout: 60_000 })
    await review.getByRole('checkbox').check()
    const doneBefore = await readDoneEventCount(this.page)
    await review.getByRole('button', { name: 'Submit inquiry' }).click()
    await this.waitForTurnDone(doneBefore)
  }

  /** Waits until the newest bot bubble shows text; WebKit can read empty right after a turn. */
  private async settledBubbles(): Promise<Locator> {
    const bubbles = this.page.getByTestId('bot-bubble-text')
    await expect(bubbles.last()).toHaveText(/\S/, { timeout: 10_000 })
    return bubbles
  }

  async lastReply(): Promise<string> {
    const replies = await this.allReplies()
    return replies[replies.length - 1]
  }

  /**
   * Reply text from the DOM, not layout: innerText came back "" for the newest bubble in CI's
   * Linux WebKit (mobile) even though the text was there. Paragraphs and list items are joined
   * with newlines so sentence checks still see the breaks.
   */
  async allReplies(): Promise<string[]> {
    const bubbles = await this.settledBubbles()
    return bubbles.evaluateAll((els) =>
      els.map((el) => {
        const blocks = Array.from(el.querySelectorAll('p, li'))
        const parts = blocks.length ? blocks.map((b) => b.textContent ?? '') : [el.textContent ?? '']
        return parts.join('\n').trim()
      }),
    )
  }

  userContext() {
    return this.userSoFar
  }

  cards(type: string): Locator {
    if (type === 'confirm_fields') return this.page.locator('[data-testid^="confirm-fields-"]')
    if (type === 'verification') return this.page.getByTestId('verification-card')
    if (type === 'document_upload') return this.page.getByTestId('document-checklist-card')
    if (type === 'mall_picker') return this.page.getByTestId('mall-picker-card')
    if (type === 'review') return this.page.getByTestId('review-card')
    if (type === 'success') return this.page.getByTestId('success-card')
    return this.page.locator(`[data-card-type="${type}"]`)
  }

  async draft(): Promise<Record<string, unknown>> {
    expect(this.sessionId).toBeTruthy()
    const res = await this.page.request.get(`http://127.0.0.1:8000/api/sessions/${this.sessionId}/draft`)
    expect(res.ok()).toBeTruthy()
    return res.json()
  }

  async events(): Promise<CapturedSseEvent[]> {
    return readCapturedEvents(this.page)
  }

}
