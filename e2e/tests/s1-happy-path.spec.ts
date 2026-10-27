import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { afterTurnChecks, finishA11y } from '../support/turnChecks'

const EMAIL = 'sara@beanstreet.example'
const MOBILE = '+966501234567'

test.describe('Story S1 @scripted', () => {
  test('front-load, inbox verify link, submit and tracking page', async ({ page, request }, testInfo) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)

    const inquiry = new InquiryPage(page)
    await inquiry.open('s1-happy-path')
    await inquiry.say('1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.confirmCard()
    await afterTurnChecks(inquiry)
    await inquiry.say(
      'Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567',
    )
    await afterTurnChecks(inquiry)
    await inquiry.confirmCard()
    await afterTurnChecks(inquiry)
    await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })

    const verifyMessages = await fetchDevOutbox(request, EMAIL)
    expect(latestByTemplate(verifyMessages, 'email_verification_link')).toBeTruthy()

    await inquiry.verifyEmailFromInbox(EMAIL)

    const smsMessages = await fetchDevOutbox(request, MOBILE)
    const sms = latestByTemplate(smsMessages, 'sms_otp')
    expect(sms).toBeTruthy()
    const codeMatch = sms?.body.match(/\b(\d{4})\b/)
    expect(codeMatch?.[1]).toBeTruthy()
    await inquiry.enterCode(codeMatch![1])

    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.upload('Company Profile', 'company_profile.pdf')
    await inquiry.upload('Brand Profile', 'brand_profile.pdf')
    await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
    await inquiry.acceptAndSubmit()
    await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
    await finishA11y(inquiry, testInfo.project.name)

    const submissionMail = latestByTemplate(await fetchDevOutbox(request, EMAIL), 'submission_email')
    expect(submissionMail).toBeTruthy()
    const trackHref = submissionMail?.links.find((l) => l.includes('/inquiry/status/'))
    expect(trackHref).toBeTruthy()

    await page.goto(trackHref!)
    await expect(page.getByTestId('inquiry-status-page')).toBeVisible()
    await expect(page.getByText(/waiting for review/i)).toBeVisible()
    await expect(page.getByText('Inquiry submitted')).toBeVisible()
  })
})
