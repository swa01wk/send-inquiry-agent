import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { afterTurnChecks } from '../support/turnChecks'

const EMAIL = 'sara@beanstreet.example'
const MOBILE = '+966501234567'

// Story S2 (L3 §3.13): the tab is closed at the verification card; the emailed link is
// opened on a second device (a new browser context) and the inquiry is finished there.
// Same scripted model as S1: the session keeps its place in the script across devices.
test.describe('Story S2 @scripted', () => {
  test('closes the tab at verification and finishes on a second device', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)

    const first = new InquiryPage(page)
    await first.open('s1-happy-path')
    await first.say('1010123456')
    await afterTurnChecks(first)
    await first.confirmCard()
    await first.say(
      'Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567',
    )
    await first.confirmCard()
    await expect(first.cards('verification')).toBeVisible({ timeout: 60_000 })
    const viewport = page.viewportSize()
    await page.close()

    // Second device: nothing shared with the first context but the emailed link.
    const device = await browser.newContext(viewport ? { viewport } : {})
    try {
      const page2 = await device.newPage()
      const second = new InquiryPage(page2)
      await second.verifyEmailFromInbox(EMAIL)
      // The chat is restored where the user left off.
      await expect(page2.getByText('Got your CR — check the company card.')).toBeVisible()
      await expect(page2.getByText(/sara@beanstreet\.example/).first()).toBeVisible()

      const sms = latestByTemplate(await fetchDevOutbox(request, MOBILE), 'sms_otp')
      const code = sms?.body.match(/\b(\d{4})\b/)?.[1]
      expect(code).toBeTruthy()
      await second.enterCode(code!)

      await expect(second.cards('document_upload')).toBeVisible({ timeout: 90_000 })
      await second.upload('Company Profile', 'company_profile.pdf')
      await second.upload('Brand Profile', 'brand_profile.pdf')
      await second.acceptAndSubmit()
      await expect(second.cards('success')).toBeVisible({ timeout: 60_000 })
    } finally {
      await device.close()
    }
  })
})
