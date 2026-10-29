import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { APPLICANT_EMAIL, reviewerFor, submitScriptedInquiry } from '../support/submit'

/** Day 4 story T2: reviewer requests a re-upload; applicant answers from the case link. */
test.describe('Story T2 @scripted', () => {
  test('re-upload loop through the reviewer console and case chat', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const reviewer = await reviewerFor(request, reference)

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

      const reupload = reviewerPage.getByTestId('action-request_reupload')
      await reupload.getByRole('checkbox', { name: 'Brand Profile' }).check()
      await reupload.locator('#reupload-remarks').fill('The logo page is missing')
      await reupload.getByRole('button', { name: 'Request re-upload' }).click()
      await expect(reviewerPage.getByTestId('case-stage')).toContainText('waiting for re-upload')

      await expect
        .poll(async () =>
          latestByTemplate(await fetchDevOutbox(request, APPLICANT_EMAIL), 'reupload_request'),
        )
        .toBeTruthy()
      const mail = latestByTemplate(
        await fetchDevOutbox(request, APPLICANT_EMAIL),
        'reupload_request',
      )!
      const casePath = mail.links.find((l) => l.includes('/inquiry/case'))
      expect(casePath).toBeTruthy()
      const caseUrl = new URL(casePath!)
      caseUrl.searchParams.set('e2eCaseScenario', 't2-reupload')

      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await expect(
        applicantPage.getByRole('region', { name: /leasing assistant chat/i }),
      ).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })
      await expect(applicant.cards('document_upload')).toBeVisible({ timeout: 60_000 })

      const uploadCard = applicant.cards('document_upload')
      await expect(uploadCard).toHaveAttribute('data-mode', 'reupload')
      await expect(uploadCard.getByText('The logo page is missing')).toBeVisible()
      await expect(uploadCard.getByText('Brand Profile')).toBeVisible()
      await expect(uploadCard.getByText('Company Profile')).toHaveCount(0)
      await expect(applicant.cards('confirm_fields')).toHaveCount(0)

      await applicant.upload('Brand Profile', 'brand_profile.pdf')
      await applicant.resubmitDocuments()

      await expect(applicant.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
        'First review',
      )
      await expect(applicant.lastReply()).resolves.toContain(
        'Thanks, your documents are back with the leasing team for first review.',
      )
      await expect(applicant.cards('confirm_fields')).toHaveCount(0)

      await reviewerPage.reload()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('First review')
      await expect(reviewerPage.getByTestId('timeline')).toContainText('Documents resubmitted')
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })
})
