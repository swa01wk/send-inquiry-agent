import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { APPLICANT_EMAIL, reviewerFor, submitScriptedInquiry } from '../support/submit'

const OMAR_EMAIL = 'omar@beanstreet.example'

/** Day 5 story T1: first approval → contacts → final approval → Yardi and tracking. */
test.describe('Story T1 @scripted', () => {
  test('lifecycle through contacts to Yardi and the tracking page', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const reviewer = await reviewerFor(request, reference)

    const submissionMail = latestByTemplate(
      await fetchDevOutbox(request, APPLICANT_EMAIL),
      'submission_email',
    )!
    const trackHref = submissionMail.links.find((l) => l.includes('/inquiry/status/'))
    expect(trackHref).toBeTruthy()

    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    const applicantContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewerPage = await reviewerContext.newPage()
      await reviewerPage.goto('/review')
      await reviewerPage.getByLabel('Reviewer').selectOption(reviewer.id)
      await reviewerPage.getByRole('button', { name: 'Sign in' }).click()
      await expect(reviewerPage.getByTestId('signed-in-reviewer')).toContainText(reviewer.name)
      await reviewerPage
        .getByTestId(`queue-row-${reference}`)
        .getByRole('link', { name: reference })
        .click()

      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('First review')
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
      const contactsMail = latestByTemplate(
        await fetchDevOutbox(request, APPLICANT_EMAIL),
        'contacts_request',
      )!
      const casePath = contactsMail.links.find((l) => l.includes('/inquiry/case'))
      expect(casePath).toBeTruthy()
      const caseUrl = new URL(casePath!)
      caseUrl.searchParams.set('e2eCaseScenario', 't1-contacts')

      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await expect(
        applicantPage.getByRole('region', { name: /leasing assistant chat/i }),
      ).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })

      await applicant.say(
        "I'm the signatory; billing is Omar Saleh, omar@beanstreet.example, +966551234567",
      )
      await expect(applicant.lastReply()).resolves.toContain(
        'Authorized Signatory and Omar Saleh as Billing Contact',
      )
      await expect(applicant.cards('contacts')).toBeVisible({ timeout: 60_000 })
      const contactsCard = applicant.cards('contacts')
      await expect(contactsCard.getByText('Authorized Signatory', { exact: true })).toBeVisible()
      await expect(contactsCard.getByText('Billing Contact', { exact: true })).toBeVisible()
      await expect(contactsCard.getByText('Omar Saleh')).toBeVisible()
      await expect(contactsCard.getByText('Same as primary contact')).toBeVisible()
      await applicant.submitContacts()
      await expect(applicant.lastReply()).resolves.toContain(
        'Thanks, your contacts are with the leasing team.',
      )

      await reviewerPage.reload()
      await expect(reviewerPage.getByTestId('approval-blockers')).toHaveCount(0)
      await expect(reviewerPage.getByTestId('action-approve')).toBeVisible()
      await reviewerPage.getByTestId('action-approve').getByRole('button', { name: 'Approve' }).click()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
      await expect(reviewerPage.getByTestId('timeline')).toContainText(/lead/i)

      await expect
        .poll(async () =>
          latestByTemplate(await fetchDevOutbox(request, APPLICANT_EMAIL), 'inquiry_accepted'),
        )
        .toBeTruthy()
      await expect
        .poll(async () =>
          latestByTemplate(await fetchDevOutbox(request, OMAR_EMAIL), 'azure_ad_invitation'),
        )
        .toBeTruthy()

      await applicantPage.goto(trackHref!)
      await expect(applicantPage.getByTestId('inquiry-status-page')).toBeVisible()
      await expect(applicantPage.getByText(/Approved — your details are with the leasing team for a proposal/i)).toBeVisible()
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })
})
