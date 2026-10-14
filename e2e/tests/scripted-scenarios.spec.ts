import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'

const SCENARIOS = [
  '02-front-loader',
  '03-no-cr',
  '04-typos',
  '05-arabic',
  '06-whatsapp',
  '07-phone-formats',
  '08-city-only',
  '09-changes-mind',
  '10-unsure',
  '11-impatient',
  '12-wrong-code',
  '14-wants-person',
  '15-asks-price',
  '16-existing-tenant',
  '17-rambler',
  '21-unclear',
  '22-lost-midway',
] as const

for (const scenario of SCENARIOS) {
  test(`${scenario} @scripted`, async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open(scenario)
    await inquiry.say('hello')
    await expect(page.getByTestId('bot-bubble-text').first()).toBeVisible()
    const draft = await inquiry.draft()
    expect(draft.phase).toBeTruthy()
  })
}
