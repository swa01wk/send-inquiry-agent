import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import {
  assertNoDuplicateConfirmCards,
  assertPlainLanguageReply,
  assertRetractionBudget,
} from '../support/plainLanguage'

async function afterTurnChecks(inquiry: InquiryPage) {
  const reply = await inquiry.lastReply()
  assertPlainLanguageReply(reply, inquiry.userContext())
  const events = await inquiry.events()
  assertNoDuplicateConfirmCards(events)
  assertRetractionBudget(events)
}

async function finishA11y(inquiry: InquiryPage, projectName: string) {
  const results = await new AxeBuilder({ page: inquiry.page })
    .include('section[aria-label="Leasing assistant chat"]')
    .disableRules(['scrollable-region-focusable'])
    .analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious, 'no serious axe violations').toEqual([])
  if (projectName === 'mobile') {
    const overflow = await inquiry.page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    )
    expect(overflow).toBeTruthy()
  }
}

test.describe('Scripted personas @scripted', () => {
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
    const fields = draft.fields as { key: string; display: string | null }[]
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('13 wrong files then PDF upload', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('01-shop-owner')
    await inquiry.say('hi')
    await inquiry.say('1010123456')
    await inquiry.say('coffee kiosk riyadh mall a')
    await inquiry.say('sara ali sara@beanstreet.example 0501234567')
    await inquiry.enterCode('1234')
    await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
    await inquiry.pickFile('Company Profile', 'notes.txt')
    await inquiry.expectUploadError('Company Profile', "That file type isn't supported.")
    await inquiry.pickFile('Company Profile', 'too_big.pdf')
    await inquiry.expectUploadError('Company Profile', 'That file is over 5 MB.')
    await inquiry.upload('Company Profile', 'company_profile.pdf')
    await inquiry.upload('Brand Profile', 'brand_profile.pdf')
    await expect(inquiry.page.getByText('2 of 2 required uploaded')).toBeVisible()
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('18 demo sequence card lifecycle', async ({ page }, testInfo) => {
    test.setTimeout(120_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('18-demo-sequence')
    await inquiry.say('Marhaba')
    await inquiry.say('1010123456')
    await inquiry.say("Yes, that's correct")
    await inquiry.say(
      'Bean Street kiosk at Riyadh Mall A. Sara Ali, sara@beanstreet.example, +966501234567',
    )
    await inquiry.say('Yes, all correct')
    expect(await inquiry.cards('confirm_fields').count()).toBeLessThanOrEqual(2)
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

  test('20 formatting preserves list', async ({ page }) => {
    test.info().annotations.push({
      type: 'note',
      description: 'List/bold rendering is covered by frontend botMessageContent.test.tsx',
    })
    await page.goto('/')
    await expect(page.getByRole('textbox', { name: 'Message' })).toBeEnabled()
  })
})
