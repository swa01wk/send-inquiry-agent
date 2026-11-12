import { expect, test } from '@playwright/test'
import { expectFlowPath, seedFlowCase, mailForCase } from '../../support/flowV2'
import { latestByTemplate } from '../../support/outbox'
import { InquiryPage } from '../../pages/inquiry'
import { openCaseAs } from '../../support/stories'

/**
 * S24 "Yes, that's me" (flow v2 §3.7, E3; docs/flow-v2/scenarios.json): after Approve Lead the
 * signatory question comes first; Yes copies the primary contact as the Authorized Signatory,
 * the tenant adds the Billing Contact, and the final Approve Lead opens.
 */
test.describe('S24 Signatory is the primary contact @flow-v2 @scripted', () => {
  test('Yes copies the primary contact; billing; Approve Lead', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    const seeded = await seedFlowCase(request, 'lead_approved')
    expect(seeded.status).toBe('lead_approved')
    const reference = seeded.reference

    const mail = latestByTemplate(
      await mailForCase(request, seeded.applicant_email, reference),
      'contacts_request',
    )
    const link = mail?.links.find((l) => l.includes('/inquiry/case'))
    expect(link).toBeTruthy()
    const caseUrl = new URL(link!)
    caseUrl.searchParams.set('e2eCaseScenario', 'flow-v2-s24')

    const applicantContext = await browser.newContext()
    try {
      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await applicant.waitForChatReady()
      await expect(applicant.cards('signatory_question')).toBeVisible({ timeout: 60_000 })
      await applicant.answerSignatoryQuestion(true)
      await expect(applicant.cards('signatory_question')).toContainText(
        "Yes, I'm the authorised signatory",
      )
      const contacts = applicant.cards('contacts')
      await expect(contacts.getByText('Same as primary contact')).toBeVisible({ timeout: 60_000 })
      await applicant.say('Ready for billing details.')
      await expect(contacts.getByTestId('contact-row-billing_contact')).toContainText('@', {
        timeout: 60_000,
      })
      await applicant.submitContacts()
    } finally {
      await applicantContext.close()
    }

    await openCaseAs(page, { id: seeded.final_reviewer!, name: '' }, reference)
    await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
    await expect(page.getByTestId('approve-lead-final')).toBeEnabled()
    await page.getByTestId('approve-lead-final').click()
    await expect(page.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')

    await expectFlowPath(request, reference, [
      ['approve_lead', 'req_contacts', 'contacts_notify', 'contacts_provide', 'approve_lead2'],
    ])
  })
})
