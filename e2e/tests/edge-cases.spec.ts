import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { draftFields, fieldDisplay } from '../support/draft'
import { afterTurnChecks, finishA11y } from '../support/turnChecks'

test.describe('Edge cases @scripted', () => {
  test('03 no CR path', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('03-no-cr')
    await inquiry.say('what is CR?')
    await afterTurnChecks(inquiry)
    const crReply = await inquiry.lastReply()
    expect(crReply.split(/[.!?]+/).filter((s) => s.trim()).length).toBeLessThanOrEqual(2)
    await inquiry.say('i dont have it')
    await afterTurnChecks(inquiry)
    await inquiry.say('Acme Trading LLC, King Abdullah Road Riyadh')
    await afterTurnChecks(inquiry)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toMatch(/Acme/i)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('08 city only mall picker', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('08-city-only')
    await inquiry.say('sneakers shop somewhere in jeddah')
    await afterTurnChecks(inquiry)
    await expect(inquiry.cards('mall_picker')).toBeVisible()
    let draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'malls') ?? '').toBeFalsy()
    await inquiry.pickMalls(['Jeddah Mall A'])
    draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'malls')).toMatch(/Jeddah Mall A/i)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('10 unsure category', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('10-unsure')
    await inquiry.say('1010123456')
    await afterTurnChecks(inquiry)
    await inquiry.say('Bean Street kiosk riyadh mall a')
    await afterTurnChecks(inquiry)
    await inquiry.say('not sure about the category')
    await afterTurnChecks(inquiry)
    const cat = draftFields(await inquiry.draft()).find((f) => f.key === 'sales_category')
    expect(cat?.confirmed).toBe(false)
    const reply = await inquiry.lastReply()
    expect(reply.toLowerCase()).toMatch(/category|option|pick|choose|food|fashion|closest/)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('15 asks price no invented SAR', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('15-asks-price')
    await inquiry.say('how much is rent at riyadh mall a?')
    await afterTurnChecks(inquiry)
    const replies = await inquiry.allReplies()
    for (const r of replies) {
      expect(r).not.toMatch(/\d[\d,]*\s*SAR/i)
    }
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('16 existing tenant sign in', async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('16-existing-tenant')
    await inquiry.say('1010000000')
    await afterTurnChecks(inquiry)
    const reply = await inquiry.lastReply()
    expect(reply.toLowerCase()).toMatch(/sign in/)
    const draft = await inquiry.draft()
    expect(draft.can_submit).toBe(false)
    await finishA11y(inquiry, testInfo.project.name)
  })

  test('17 rambler paragraph', async ({ page }, testInfo) => {
    test.setTimeout(120_000)
    const inquiry = new InquiryPage(page)
    await inquiry.open('17-rambler')
    await inquiry.say(
      'Hi there CR 1010123456 we are Bean Street specialty coffee and we want a small kiosk at Riyadh Mall A budget 250k my name is Sara Ali email sara@beanstreet.example phone +966501234567 anyway the weather is nice today',
    )
    await afterTurnChecks(inquiry)
    const reply = await inquiry.lastReply()
    expect(reply.split(/[.!?]+/).filter((s) => s.trim()).length).toBeLessThanOrEqual(4)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'email')).toContain('@')
    expect(fieldDisplay(draft, 'mobile')).toContain('966')
    await finishA11y(inquiry, testInfo.project.name)
  })
})
