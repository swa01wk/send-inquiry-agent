import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fetchDevOutbox, latestByTemplate } from '../support/outbox'
import {
  OASIS_APPLICANT_EMAIL,
  openCaseAs,
  openReviewerCase,
  raiseTenantInquiry,
  signInReviewer,
} from '../support/stories'
import { approveDocumentsViaApi, approveLeadViaApi, reviewerFor } from '../support/submit'

const LAYLA_EMAIL = 'layla.hassan@oasiscoffee.example'
const OMAR_EMAIL = 'omar@beanstreet.example'

/** Day 5 C2: existing tenant through contacts, Yardi assistant, and invitations policy. */
test.describe('Story A1 approvals and Yardi @scripted', () => {
  test('Oasis: prefilled contacts, assistant Yardi match, no invite for Layla', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)

    const { reference } = await raiseTenantInquiry(
      page,
      /Oasis Coffee Company/,
      'OPP-101',
      'a1-existing-tenant',
      /Welcome back, Layla/,
    )
    const reviewer = await reviewerFor(request, reference)

    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    const applicantContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewerPage = await reviewerContext.newPage()
      await signInReviewer(reviewerPage, reviewer)
      await openReviewerCase(reviewerPage, reference)
      // Day R2: the Lease Admin approves each document first (demo feedback §3.4).
      await approveDocumentsViaApi(request, reference)
      await reviewerPage.reload()

      await reviewerPage
        .getByTestId('action-approve_first')
        .getByRole('button', { name: 'Approve first level' })
        .click()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Tenant Qualified')

      // Final review: the RSM takes over from the Leasing Admin (demo feedback §3.2), assigns
      // the unit and answers "Approve Lead?" = Yes, which opens the contacts (flow v2 §3.7).
      const finalReviewer = await reviewerFor(request, reference, 'final')
      await approveLeadViaApi(request, reference)
      await openCaseAs(reviewerPage, finalReviewer, reference)
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Lead Approved')
      // Flow v2 V14: the console has no Remove; the API event still exists for this story.
      await expect(reviewerPage.getByTestId('action-remove_contact')).toHaveCount(0)
      const removed = await request.post(
        `http://127.0.0.1:8000/api/review/cases/${encodeURIComponent(reference)}/actions`,
        {
          headers: { 'X-Reviewer-Id': finalReviewer.id },
          data: { action: 'remove_contact', payload: { role: 'billing_contact' } },
        },
      )
      expect(removed.ok()).toBeTruthy()

      await expect
        .poll(async () =>
          latestByTemplate(
            await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
            'contacts_request',
          ),
        )
        .toBeTruthy()
      const contactsMail = latestByTemplate(
        await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
        'contacts_request',
      )!
      const casePath = contactsMail.links.find((l) => l.includes('/inquiry/case'))
      expect(casePath).toBeTruthy()
      const caseUrl = new URL(casePath!)
      caseUrl.searchParams.set('e2eCaseScenario', 't1-contacts')

      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await applicant.waitForChatReady()
      await applicant.say(
        "I'm the signatory; billing is Omar Saleh, omar@beanstreet.example, +966551234567",
      )
      await expect(applicant.cards('contacts')).toBeVisible({
        timeout: 60_000,
      })
      await applicant.submitContacts()

      await reviewerPage.goto(
        `/review/cases/${encodeURIComponent(reference)}?e2eScenario=r1-yardi-suggest`,
      )
      const assistant = reviewerPage.getByTestId('reviewer-assistant-panel')
      await assistant.getByLabel('Message').fill('Find the Yardi company for Bean Street Trading.')
      await assistant.getByRole('button', { name: 'Send' }).click()
      const suggestion = reviewerPage
        .getByTestId('reviewer-suggestion')
        .filter({ hasText: /Bean Street Trading Co\./ })
      await expect(suggestion).toBeVisible({ timeout: 60_000 })
      await suggestion.getByRole('button', { name: 'Use' }).click()
      const yardi = reviewerPage.getByTestId('action-yardi')
      await expect(yardi.getByLabel('Company')).toHaveValue('YC-1001')
      await expect(yardi.getByLabel('Company')).toContainText('Bean Street Trading Co.')
      await yardi.getByRole('button', { name: 'Link company' }).click()
      await expect(yardi.getByTestId('yardi-linked')).toContainText('YC-1001')

      // Flow v2: no per-contact approval; the final Approve Lead once both contacts are in.
      await reviewerPage.reload()
      await expect(reviewerPage.getByTestId('approve-lead-final')).toBeEnabled()
      await reviewerPage.getByTestId('approve-lead-final').click()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')

      expect(
        (await fetchDevOutbox(request, LAYLA_EMAIL)).filter(
          (m) => m.template === 'azure_ad_invitation',
        ),
      ).toHaveLength(0)
      await expect
        .poll(async () =>
          latestByTemplate(await fetchDevOutbox(request, OMAR_EMAIL), 'azure_ad_invitation'),
        )
        .toBeTruthy()

      const submissionMail = latestByTemplate(
        await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
        'submission_email',
      )
      const trackHref = submissionMail?.links.find((l) => l.includes('/inquiry/status/'))
      expect(trackHref).toBeTruthy()
      await applicantPage.goto(trackHref!)
      await expect(applicantPage.getByTestId('inquiry-status-page')).toBeVisible()
      await expect(applicantPage.getByText('Tenant Qualified')).toBeVisible()
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })
})
