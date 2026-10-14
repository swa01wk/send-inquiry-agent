import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fieldDisplay, fieldSource } from '../support/draft'
import { afterTurnChecks, finishA11y } from '../support/turnChecks'

test.describe('Basics @scripted', () => {
  test('01 shop owner brief path', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('01-shop-owner')
    await inquiry.say('hi')
    await afterTurnChecks(inquiry)
    await inquiry.say('1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.say('coffee kiosk riyadh mall a')
    await afterTurnChecks(inquiry)
    await inquiry.say('sara ali sara@beanstreet.example 0501234567')
    await afterTurnChecks(inquiry)
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'malls')).toMatch(/Riyadh Mall A/i)
    expect(fieldDisplay(draft, 'unit_type')).toBeTruthy()
    expect(fieldDisplay(draft, 'sales_category')).toBeTruthy()
    expect(fieldDisplay(draft, 'first_name')).toMatch(/Sara/i)
    expect(fieldDisplay(draft, 'last_name')).toMatch(/Ali/i)
    expect(fieldDisplay(draft, 'mobile')).toContain('+966501234567')
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('02 front-loader one bulk message', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('02-front-loader')
    await inquiry.say('1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.say(
      'Bean Street kiosk Riyadh Mall A 30 sqm budget 250k 3 year lease Sara Ali sara@beanstreet.example 0501234567',
    )
    await afterTurnChecks(inquiry)
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
    const replies = await inquiry.allReplies()
    const last = replies[replies.length - 1] ?? ''
    expect(last.toLowerCase()).not.toMatch(/what is your (email|phone|name)/)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('07 phone formats normalize mobile', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('07-phone-formats')
    await inquiry.say('1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.say('Bean Street kiosk riyadh mall a')
    await afterTurnChecks(inquiry)
    await inquiry.say('Sara Ali sara@beanstreet.example 05 0123 4567')
    await afterTurnChecks(inquiry)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'mobile')).toBe('+966501234567')
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('18 demo sequence cards and submit', async ({ page }, testInfo) => {
    test.setTimeout(180_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('18-demo-sequence')
    const demoTurns = [
      'Marhaba',
      'My CR number is 1010123456',
      "Yes, that's correct",
      'Bean Street specialty coffee kiosk at Riyadh Mall A — about 30 sqm, budget up to 250,000 SAR per year, 3-year lease. Sara Ali, sara@beanstreet.example, +966501234567',
      'Yes, all correct',
      'Actually we want a full store unit, not specialty or kiosk.',
      'What documents do I need to upload?',
      'Can I review and submit now?',
    ]
    for (const text of demoTurns) {
      await inquiry.say(text)
      await afterTurnChecks(inquiry)
    }
    const repliesBeforeCoffee = await inquiry.allReplies()
    expect(repliesBeforeCoffee.some((r) => /Company Profile/i.test(r) && /Brand Profile/i.test(r))).toBeTruthy()
    for (const r of repliesBeforeCoffee.slice(0, 3)) {
      expect(r.toLowerCase()).not.toContain('coffee')
    }
    const companyCards = inquiry.page.locator('[data-testid^="confirm-fields-"]').filter({ hasText: 'From your CR' })
    await expect(companyCards).toHaveCount(1)
    await expect(companyCards.first().getByRole('button', { name: 'Looks right' })).toHaveCount(0)
    const brandCards = inquiry.page.locator('[data-testid^="confirm-fields-"]').filter({ hasText: 'Bean Street' })
    await expect(brandCards).toHaveCount(1)
    const draftMid = await inquiry.draft()
    expect(fieldSource(draftMid, 'unit_type')).toBe('user')
    expect(fieldDisplay(draftMid, 'unit_type')).toMatch(/store/i)
    await inquiry.enterCode('1234')
    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.upload('Company Profile', 'company_profile.pdf')
    await inquiry.upload('Brand Profile', 'brand_profile.pdf')
    await inquiry.say('ok both pdfs uploaded')
    await afterTurnChecks(inquiry)
    await inquiry.acceptAndSubmit()
    await expect(inquiry.cards('success')).toBeVisible({ timeout: 60_000 })
    const refText = await inquiry.page.getByTestId('success-card').innerText()
    expect(refText).toMatch(/GEO-(STR|MED|SPC|OFF)-\d{6}/)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('19 CR chip focuses composer without chat', async ({ page }) => {
    let chatPosts = 0
    await page.route('**/api/sessions/*/chat', (route) => {
      chatPosts += 1
      return route.continue()
    })
    const inquiry = new InquiryPage(page)
    await inquiry.open('19-cr-chip')
    await inquiry.tapChip('I have my CR number')
    expect(chatPosts).toBe(0)
    await expect(page.getByRole('textbox', { name: 'Message' })).toHaveAttribute(
      'placeholder',
      /10-digit CR number/i,
    )
  })
})
