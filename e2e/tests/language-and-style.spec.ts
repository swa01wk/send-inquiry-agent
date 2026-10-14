import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fieldDisplay } from '../support/draft'
import { countRetractions } from '../support/events'
import { afterTurnChecks, finishA11y } from '../support/turnChecks'

test.describe('Language and style @scripted', () => {
  test('05 Arabic user', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('05-arabic')
    await inquiry.say('السلام عليكم')
    await afterTurnChecks(inquiry)
    await inquiry.say('رقم السجل 1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.say('كشك قهوة في Riyadh Mall A اسم العلامة بين ستريت')
    await afterTurnChecks(inquiry)
    await inquiry.say('سارة علي sara@beanstreet.example 0501234567')
    await afterTurnChecks(inquiry)
    const replies = await inquiry.allReplies()
    expect(replies.some((r) => /[\u0600-\u06FF]/.test(r))).toBeTruthy()
    expect(countRetractions(await inquiry.events())).toBeLessThanOrEqual(1)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'email')).toContain('@')
    expect(fieldDisplay(draft, 'mobile')).toContain('966')
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('06 WhatsApp style', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('06-whatsapp')
    await inquiry.say('hiii 👋 pls help')
    await afterTurnChecks(inquiry)
    await inquiry.say('cr 1010123456 🙏')
    await afterTurnChecks(inquiry)
    await inquiry.say('we sell coffee ☕ small kiosk riyadh mall a')
    await afterTurnChecks(inquiry)
    await inquiry.say('Sara Ali sara@beanstreet.example 0501234567')
    await afterTurnChecks(inquiry)
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'brand_name_en')).toBeTruthy()
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('20 bullet list renders as ul', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('20-formatting')
    await inquiry.say('hello')
    await afterTurnChecks(inquiry)
    const list = page.getByTestId('bot-bubble-text').last().locator('ul')
    await expect(list).toBeVisible()
    await expect(list.locator('li')).toHaveCount(2)
    await expect(list.locator('li').nth(0)).toContainText('First point')
    await expect(list.locator('li').nth(1)).toContainText('Second point')
    await finishA11y(inquiry, testInfo.project.name)
  })
})
