import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { afterTurnChecks, finishA11y } from '../support/turnChecks'

test.describe('Story S14 @scripted', () => {
  test('documents before email verification', async ({ page }, testInfo) => {
    test.setTimeout(240_000)

    const inquiry = new InquiryPage(page)
    await inquiry.open('s14-out-of-order')
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

    await inquiry.enterCode('1234')
    await inquiry.upload('Company Profile', 'company_profile.pdf')
    await inquiry.upload('Brand Profile', 'brand_profile.pdf')

    await expect(inquiry.cards('review')).toHaveCount(0)
    const reply = await inquiry.lastReply()
    expect(reply.toLowerCase()).toMatch(/email|link/)

    await expect(page.getByTestId('stage-documents')).toHaveAttribute('data-state', 'done')
    await expect(page.getByTestId('stage-contact')).toHaveAttribute('data-state', 'current')

    await page.getByTestId('stage-contact').click()
    await expect(inquiry.cards('verification')).toBeInViewport()

    await inquiry.verifyEmail()
    await expect(inquiry.cards('review')).toBeVisible({ timeout: 60_000 })
    await finishA11y(inquiry, testInfo.project.name)
  })
})
