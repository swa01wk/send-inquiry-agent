import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { draftFields, fieldDisplay } from '../support/draft'
import { countRetractions } from '../support/events'
import { appendLiveResult, type LiveScenarioResult } from '../support/liveResults'
import { afterTurnChecks } from '../support/turnChecks'

test.describe('Live OpenAI personas @live', () => {
  test.skip(!process.env.OPENAI_API_KEY, 'OPENAI_API_KEY required')

  test.afterEach(async ({}, testInfo) => {
    if (!process.env.OPENAI_API_KEY) return
    const result: LiveScenarioResult = {
      scenario: testInfo.title,
      pass: testInfo.status === 'passed',
      turns: 0,
      retractions: 0,
      durationMs: testInfo.duration,
      error: testInfo.error?.message,
    }
    await appendLiveResult(result)
  })

  async function trackTurns(inquiry: InquiryPage, text: string) {
    await inquiry.say(text)
    await afterTurnChecks(inquiry)
  }

  test('01 shop owner @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'hi')
    await trackTurns(inquiry, '1010123456')
    await trackTurns(inquiry, 'coffee kiosk riyadh mall a')
    await trackTurns(inquiry, 'sara ali sara@beanstreet.example 0501234567')
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'malls')).toBeTruthy()
    expect(fieldDisplay(draft, 'mobile')).toMatch(/966/)
  })

  test('02 front loader @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, '1010123456')
    await trackTurns(
      inquiry,
      'Bean Street kiosk Riyadh Mall A Sara Ali sara@beanstreet.example 0501234567',
    )
    expect(await inquiry.cards('otp_input').count()).toBeGreaterThan(0)
  })

  test('03 no CR @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'what is CR?')
    await trackTurns(inquiry, 'i dont have it')
    await trackTurns(inquiry, 'Acme Trading LLC, King Abdullah Road Riyadh')
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toBeTruthy()
  })

  test('05 Arabic @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'السلام عليكم')
    await trackTurns(inquiry, 'رقم السجل 1010123456')
    await trackTurns(inquiry, 'كشك قهوة في Riyadh Mall A')
    await trackTurns(inquiry, 'سارة علي sara@beanstreet.example 0501234567')
    const replies = await inquiry.allReplies()
    expect(replies.some((r) => /[\u0600-\u06FF]/.test(r))).toBeTruthy()
    expect(countRetractions(await inquiry.events())).toBeLessThanOrEqual(1)
  })

  test('06 WhatsApp @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'hiii 👋 pls help')
    await trackTurns(inquiry, 'cr 1010123456 🙏')
    await trackTurns(inquiry, 'we sell coffee ☕ small kiosk riyadh mall a')
    await trackTurns(inquiry, 'Sara Ali sara@beanstreet.example 0501234567')
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'brand_name_en')).toBeTruthy()
  })

  test('09 changes mind @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, '1010123456')
    await trackTurns(inquiry, 'Bean Street kiosk riyadh mall a')
    await trackTurns(inquiry, 'actually make it a full shop not kiosk')
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'unit_type')).toMatch(/store/i)
  })

  test('10 unsure category @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, '1010123456')
    await trackTurns(inquiry, 'Bean Street kiosk riyadh mall a')
    await trackTurns(inquiry, 'not sure about the category')
    const cat = draftFields(await inquiry.draft()).find((f) => f.key === 'sales_category')
    expect(cat?.confirmed).toBe(false)
  })

  test('11 impatient @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'just submit it')
    expect(await inquiry.cards('success').count()).toBe(0)
    expect(await inquiry.cards('review').count()).toBe(0)
  })

  test('14 wants person @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'can i talk to someone?')
    const reply = await inquiry.lastReply()
    expect(reply.length).toBeGreaterThan(5)
  })

  test('15 asks price @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, 'how much is rent at riyadh mall a?')
    const replies = await inquiry.allReplies()
    expect(replies.join(' ')).not.toMatch(/\d[\d,]*\s*SAR/i)
  })

  test('17 rambler @live', async ({ page }) => {
    test.setTimeout(180_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(
      inquiry,
      'Hi Bean Street coffee kiosk Riyadh Mall A Sara Ali sara@beanstreet.example +966501234567 and then I went to the park',
    )
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'email')).toContain('@')
  })

  test('18 demo path @live', async ({ page }) => {
    test.setTimeout(240_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    const turns = [
      'Marhaba',
      'My CR number is 1010123456',
      "Yes, that's correct",
      'Bean Street kiosk at Riyadh Mall A Sara Ali sara@beanstreet.example +966501234567',
      'Yes, all correct',
      'Actually we want a full store unit',
      'What documents do I need?',
    ]
    for (const t of turns) await trackTurns(inquiry, t)
    expect(await inquiry.cards('confirm_fields').count()).toBeGreaterThan(0)
  })

  test('21 unclear @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    for (const t of ['i want shop', '?', 'idk']) await trackTurns(inquiry, t)
    const reply = await inquiry.lastReply()
    expect(reply.split(/[.!?]+/).filter((s) => s.trim()).length).toBeLessThanOrEqual(3)
  })

  test('22 lost mid-way @live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await trackTurns(inquiry, '1010123456')
    await trackTurns(inquiry, 'Bean Street kiosk riyadh mall a')
    const before = await inquiry.draft()
    await trackTurns(inquiry, 'what? i dont understand')
    await trackTurns(inquiry, 'what do i do now')
    const after = await inquiry.draft()
    expect(JSON.stringify(before.fields)).toBe(JSON.stringify(after.fields))
  })
})
