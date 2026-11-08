import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fetchDevAudit, readDoneEventCount } from '../support/events'
import { fieldDisplay } from '../support/draft'
import { afterTurnChecks } from '../support/turnChecks'

const TYPED_CR = '1010000000'

test.describe('Re-demo CR question @scripted', () => {
  test('Yes → sign-in card → /tenant (Leasing Opportunities)', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-cr-question')
    await expect(inquiry.cards('cr_question')).toBeVisible()
    const doneBefore = await readDoneEventCount(page)
    await inquiry
      .cards('cr_question')
      .getByRole('button', { name: /yes, we have a cr/i })
      .click()
    await inquiry.waitForTurnDone(doneBefore)
    await expect(inquiry.cards('sign_in_prompt')).toBeVisible({ timeout: 60_000 })
    const link = inquiry.cards('sign_in_prompt').getByRole('link', {
      name: /sign in to tenant central/i,
    })
    await expect(link).toHaveAttribute('href', /\/tenant\/?$/)
    await link.click()
    await expect(page.getByTestId('tenant-sign-in')).toBeVisible({ timeout: 30_000 })
    await page.getByLabel('Company').selectOption({ index: 1 })
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByTestId('tenant-signed-in')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('heading', { name: /leasing opportunities/i })).toBeVisible()
  })

  test('No → company intake questions', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-cr-question')
    await expect(inquiry.cards('cr_question')).toBeVisible()
    const doneBefore = await readDoneEventCount(page)
    await inquiry
      .cards('cr_question')
      .getByRole('button', { name: /no, we don't/i })
      .click()
    await inquiry.waitForTurnDone(doneBefore)
    await afterTurnChecks(inquiry)
    const reply = await inquiry.lastReply()
    expect(reply.toLowerCase()).toMatch(/type|upload|profile/)
    await inquiry.say('Acme Trading LLC, King Abdullah Road, Riyadh')
    await afterTurnChecks(inquiry)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'company_name')).toMatch(/Acme/i)
  })

  test('typed CR number → sign-in reply; number not in draft, SSE or audit', async ({
    page,
    request,
  }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open('rd-cr-question')
    await inquiry.say(`my CR is ${TYPED_CR}`)
    await afterTurnChecks(inquiry)
    await expect(inquiry.cards('sign_in_prompt')).toBeVisible({ timeout: 60_000 })
    const reply = await inquiry.lastReply()
    expect(reply).not.toContain(TYPED_CR)
    expect(reply.toLowerCase()).toMatch(/sign in/)
    const draft = await inquiry.draft()
    expect(fieldDisplay(draft, 'cr_number') ?? '').toBeFalsy()
    const events = await inquiry.events()
    const sseBlob = JSON.stringify(events)
    expect(sseBlob).not.toContain(TYPED_CR)
    const audit = await fetchDevAudit(request, inquiry.sessionId!)
    expect(JSON.stringify(audit)).not.toContain(TYPED_CR)
  })
})
