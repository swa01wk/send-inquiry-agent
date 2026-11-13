import { expect, test } from '@playwright/test'
import { readDoneEventCount } from '../support/events'
import { fieldDisplay } from '../support/draft'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { reviewerFor } from '../support/submit'
import {
  C1_EXISTING_CR_TURN,
  OASIS_APPLICANT_EMAIL,
  completeApplicationFromLink,
  openCallCentreChat,
  openReviewerCase,
  signInReviewer,
  staffSendApplicationLink,
} from '../support/stories'

/** A caller from Oasis whose email is not a Tenant Central login yet (c1-existing-cr). */
const NEW_CONTACT_EMAIL = 'huda.saleh@oasiscoffee.example'
const NEW_CONTACT_MOBILE = '+966507654321'

/**
 * Flow v2 (§3.4) call centre, existing CR → "Primary Contact existing?". CC1: the caller already
 * has a login → Inform, sign-in link, no inquiry. CC2: a new contact → captured fresh (M16).
 */
test.describe('Story A2 existing CR @scripted', () => {
  test.beforeEach(async ({ request }) => {
    await clearDevOutbox(request)
  })

  test('CC1 existing contact: inform and email the sign-in link, no inquiry', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    const chat = await openCallCentreChat(page, 'Sami Al Anazi', 'c1-existing-cr-sign-in')
    await chat.say(C1_EXISTING_CR_TURN)

    const check = chat.cards('contact_check')
    await expect(check).toBeVisible({ timeout: 60_000 })
    await expect(check).toContainText('Oasis Coffee Company')
    let doneBefore = await readDoneEventCount(page)
    await check.getByLabel("Caller's email").fill(OASIS_APPLICANT_EMAIL)
    await check.getByRole('button', { name: 'Check contact' }).click()
    await chat.waitForTurnDone(doneBefore)
    await expect(check).toContainText('already has a Tenant Central login')

    const inform = chat.cards('inform_tenant')
    await expect(inform).toBeVisible()
    await expect(inform).toContainText('Leasing Opportunities')
    doneBefore = await readDoneEventCount(page)
    await inform.getByRole('button', { name: 'Email sign-in link' }).click()
    await chat.waitForTurnDone(doneBefore)
    await expect(inform.getByText(/Sign-in link sent to/)).toBeVisible()

    await expect(chat.cards('send_link')).toHaveCount(0)
    const mail = await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL)
    expect(latestByTemplate(mail, 'sign_in_link')).toBeTruthy()
    expect(latestByTemplate(mail, 'complete_application')).toBeFalsy()
  })

  test('CC2 new contact: captured fresh, link, applicant submits', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    const chat = await openCallCentreChat(page, 'Sami Al Anazi', 'c1-existing-cr')
    await chat.say(C1_EXISTING_CR_TURN)

    const check = chat.cards('contact_check')
    await expect(check).toBeVisible({ timeout: 60_000 })
    const doneBefore = await readDoneEventCount(page)
    await check.getByLabel("Caller's email").fill(NEW_CONTACT_EMAIL)
    await check.getByRole('button', { name: 'Check contact' }).click()
    await chat.waitForTurnDone(doneBefore)
    await expect(check).toContainText('new contact')
    await expect(chat.cards('inform_tenant')).toHaveCount(0)

    // M16: nothing comes from the tenant record; the executive captures it.
    await chat.say('Oasis Coffee Company on King Fahd Road; Huda Saleh, 0507654321')
    const draft = await chat.draft()
    expect(fieldDisplay(draft, 'company_name')).toBe('Oasis Coffee Company')

    const verifyPath = await staffSendApplicationLink(chat, request, NEW_CONTACT_EMAIL)
    const reference = await completeApplicationFromLink(browser, request, verifyPath, page, {
      email: NEW_CONTACT_EMAIL,
      mobile: NEW_CONTACT_MOBILE,
    })

    const reviewer = await reviewerFor(request, reference)
    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewerPage = await reviewerContext.newPage()
      await signInReviewer(reviewerPage, reviewer)
      await openReviewerCase(reviewerPage, reference)
      await expect(reviewerPage.getByTestId('case-channel')).toHaveText(
        'Started by the call centre',
      )
    } finally {
      await reviewerContext.close()
    }
  })
})
