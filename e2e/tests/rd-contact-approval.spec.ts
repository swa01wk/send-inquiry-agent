import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fetchDevAudit } from '../support/events'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import {
  APPLICANT_EMAIL,
  approveContactsViaApi,
  approveDocumentsViaApi,
  reviewerFor,
  submitScriptedInquiry,
} from '../support/submit'

/**
 * Re-demo story rd-contact-approval (demo feedback §3.5, D8): signatory card, billing contact,
 * Lease Admin rejects billing, tenant fixes it, Lease Admin approves, RLM **Approve** enabled.
 */
test.describe('Story rd-contact-approval @scripted', () => {
  test('signatory Yes, billing rejection, fix, and final approval', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(360_000)
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
      caseUrl.searchParams.set('e2eCaseScenario', 'rd-contact-approval')
      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('signatory_question')).toBeVisible({ timeout: 30_000 })

      await applicant.answerSignatoryQuestion(true)
      await expect(applicant.cards('signatory_question')).toContainText(
        "Yes, I'm the authorised signatory",
      )

      const sessionId = applicant.sessionId
      expect(sessionId).toBeTruthy()
      const auditAfterYes = await fetchDevAudit(request, sessionId!)
      expect(auditAfterYes.some((e) => e.type === 'signatory_answered')).toBe(true)

      await applicant.say('Ready for billing details.')
      await expect(applicant.cards('contacts')).toBeVisible({ timeout: 60_000 })
      await applicant.submitContacts()

      await openCaseAs(reviewerPage, leaseAdmin, reference)
      await expect(reviewerPage.getByTestId('contact-approval-authorized_signatory')).toHaveText(
        'Approved',
      )
      await expect(reviewerPage.getByTestId('contact-approval-billing_contact')).toHaveText(
        'Waiting for approval',
      )

      const billing = reviewerPage.getByTestId('contact-row-billing_contact')
      await billing.getByLabel('Remarks (needed to reject)').fill('Use the finance mailbox')
      await reviewerPage.getByTestId('contact-reject-billing_contact').click()
      await expect(reviewerPage.getByTestId('contact-approval-billing_contact')).toContainText(
        'Rejected: Use the finance mailbox',
      )

      const outboxAfterReject = await expect
        .poll(async () =>
          (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
            (m) => m.template === 'contacts_request',
          ),
        )
        .toHaveLength(2)
        .then(async () => (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
          (m) => m.template === 'contacts_request',
        ))

      const fixUrl = new URL(outboxAfterReject[0].links.find((l) => l.includes('/inquiry/case'))!)
      fixUrl.searchParams.set('e2eCaseScenario', 'rd-contact-approval')
      await applicantPage.goto(fixUrl.toString())
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('contacts')).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('contacts').getByTestId('contact-approval-billing_contact')).toHaveText(
        /Needs a change.*finance mailbox/i,
      )
      await expect(
        applicant.cards('contacts').getByTestId('contact-row-authorized_signatory'),
      ).toHaveCount(0)

      await applicant.say('Here is the updated billing email.')
      await applicant.submitContacts()

      await approveContactsViaApi(request, reference)

      const rlm = await reviewerFor(request, reference, 'final')
      await openCaseAs(reviewerPage, rlm, reference)
      await expect(reviewerPage.getByTestId('action-approve').getByRole('button', { name: 'Approve' })).toBeEnabled()
      await expect(reviewerPage.getByTestId('approval-blockers')).toHaveCount(0)
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })
})
