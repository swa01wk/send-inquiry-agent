import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import {
  APPLICANT_EMAIL,
  approveDocumentsViaApi,
  reviewerFor,
  submitScriptedInquiry,
} from '../support/submit'

/**
 * Re-demo story rd-contact-approval (demo feedback §3.5, D8), console half (day R2 backend
 * PR): the applicant sends contacts, the applicant as signatory is approved on entry, the
 * Lease Admin rejects the billing contact (a contacts request reopens for that role) and the
 * RLM's **Approve** waits. The chat half (the signatory card, the tenant fixing the contact)
 * comes with the R2 Cursor track.
 */
test.describe('Story rd-contact-approval @scripted', () => {
  test('Lease Admin decides each contact; the RLM sees the chips read-only', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const leaseAdmin = await reviewerFor(request, reference, 'first')
    await approveDocumentsViaApi(request, reference)

    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    const applicantContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewerPage = await reviewerContext.newPage()
      await openCaseAs(reviewerPage, leaseAdmin, reference)
      await reviewerPage
        .getByTestId('action-approve_first')
        .getByRole('button', { name: 'Approve first level' })
        .click()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Lead — second review')

      await expect
        .poll(async () =>
          latestByTemplate(await fetchDevOutbox(request, APPLICANT_EMAIL), 'contacts_request'),
        )
        .toBeTruthy()
      const mail = latestByTemplate(
        await fetchDevOutbox(request, APPLICANT_EMAIL),
        'contacts_request',
      )!
      const caseUrl = new URL(mail.links.find((l) => l.includes('/inquiry/case'))!)
      caseUrl.searchParams.set('e2eCaseScenario', 't1-contacts')
      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })
      await applicant.say(
        "I'm the signatory; billing is Omar Saleh, omar@beanstreet.example, +966551234567",
      )
      await expect(applicant.cards('contacts')).toBeVisible({ timeout: 60_000 })
      await applicant.submitContacts()

      // The RLM: chips only, and final approval waits for the billing contact.
      const rlm = await reviewerFor(request, reference, 'final')
      await openCaseAs(reviewerPage, rlm, reference)
      await expect(reviewerPage.getByTestId('contact-approval-authorized_signatory')).toHaveText(
        'Approved',
      )
      await expect(reviewerPage.getByTestId('contact-approval-billing_contact')).toHaveText(
        'Waiting for approval',
      )
      await expect(reviewerPage.getByTestId('contact-approve-billing_contact')).toHaveCount(0)
      await expect(reviewerPage.getByTestId('action-approve')).toHaveCount(0)
      await expect(reviewerPage.getByTestId('approval-blockers')).toContainText(
        'Billing contact not approved yet',
      )

      // The Lease Admin rejects the billing contact: a contacts request reopens for it.
      await openCaseAs(reviewerPage, leaseAdmin, reference)
      const billing = reviewerPage.getByTestId('contact-row-billing_contact')
      await billing.getByLabel('Remarks (needed to reject)').fill('Use the finance mailbox')
      await reviewerPage.getByTestId('contact-reject-billing_contact').click()
      await expect(reviewerPage.getByTestId('contact-approval-billing_contact')).toContainText(
        'Rejected: Use the finance mailbox',
      )
      await expect(reviewerPage.getByTestId('requests')).toContainText('contacts · open')
      await expect
        .poll(async () =>
          (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
            (m) => m.template === 'contacts_request',
          ),
        )
        .toHaveLength(2)
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })
})
