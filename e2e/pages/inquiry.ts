import { expect, type Locator, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { clearCapturedEvents, readCapturedEvents, type CapturedSseEvent } from '../support/events'

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
    const created = this.page.waitForResponse(
      (r) => r.url().includes('/api/sessions') && r.request().method() === 'POST' && r.status() === 200,
      { timeout: 60_000 },
    )
    const url = scenario ? `/?e2eScenario=${encodeURIComponent(scenario)}` : '/'
    await this.page.goto(url)
    const res = await created
    const body = (await res.json()) as { session_id: string }
    this.sessionId = body.session_id
    await expect(this.page.getByRole('textbox', { name: 'Message' })).toBeEnabled({ timeout: 60_000 })
    await clearCapturedEvents(this.page)
  }

  async say(text: string) {
    this.userSoFar += `\n${text}`
    const box = this.page.getByRole('textbox', { name: 'Message' })
    await box.fill(text)
    await box.press('Enter')
    await this.waitForTurnDone()
  }

  async waitForTurnDone() {
    await expect(this.page.getByRole('textbox', { name: 'Message' })).toBeDisabled()
    await expect(this.page.getByRole('textbox', { name: 'Message' })).toBeEnabled({ timeout: 120_000 })
  }

  async tapChip(label: string) {
    await this.page.getByRole('button', { name: label }).click()
  }

  async confirmCard() {
    await this.page.getByRole('button', { name: 'Looks right' }).last().click()
    await this.waitForTurnDone()
  }

  async pickMalls(names: string[]) {
    for (const name of names) {
      await this.page.getByRole('button', { name, exact: true }).click()
    }
    await this.page.getByRole('button', { name: 'Done' }).click()
    await this.waitForTurnDone()
  }

  async enterCode(code: string) {
    const input = this.page.locator('#otp-code')
    await input.fill(code)
    await this.page.getByRole('button', { name: /verify/i }).click()
    await this.waitForTurnDone()
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
    await this.pickFile(docLabel, fileName)
    const card = this.page.getByTestId('document-checklist-card')
    const row = card.locator('div').filter({ hasText: docLabel }).first()
    await expect(row.getByText(/Uploaded/i)).toBeVisible({ timeout: 30_000 })
  }

  async expectUploadError(docLabel: string, message: string) {
    const card = this.page.getByTestId('document-checklist-card')
    const row = card.locator('div').filter({ hasText: docLabel }).first()
    await expect(row.getByText(message)).toBeVisible()
  }

  async acceptAndSubmit() {
    await this.page.getByRole('checkbox').check()
    await this.page.getByRole('button', { name: 'Submit inquiry' }).click()
    await this.waitForTurnDone()
  }

  async lastReply(): Promise<string> {
    const bubbles = this.page.getByTestId('bot-bubble-text')
    const n = await bubbles.count()
    expect(n).toBeGreaterThan(0)
    return (await bubbles.nth(n - 1).innerText()).trim()
  }

  async allReplies(): Promise<string[]> {
    const bubbles = this.page.getByTestId('bot-bubble-text')
    const n = await bubbles.count()
    const out: string[] = []
    for (let i = 0; i < n; i++) out.push((await bubbles.nth(i).innerText()).trim())
    return out
  }

  userContext() {
    return this.userSoFar
  }

  cards(type: string): Locator {
    if (type === 'confirm_fields') return this.page.locator('[data-testid^="confirm-fields-"]')
    if (type === 'otp_input') return this.page.getByTestId('otp-card')
    if (type === 'document_upload') return this.page.getByTestId('document-checklist-card')
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
