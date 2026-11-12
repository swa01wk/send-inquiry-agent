import { expect, test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { clearDevOutbox, fetchDevOutbox, latestByTemplate } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import { APPLICANT_EMAIL, reviewerFor, submitScriptedInquiry } from '../support/submit'

/**
 * Re-demo story rd-document-approval (demo feedback §3.4, D5, D7): the Lease Admin approves
 * the Company Profile and rejects the Brand Profile, asks for the rejected one with nothing
 * ticked, the applicant re-uploads in the case chat, and the new file needs approval again.
 */
test.describe('Story rd-document-approval @scripted', () => {
  test('reject, re-upload in the case chat, approve, then approve the first level', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const leaseAdmin = await reviewerFor(request, reference, 'first')

    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    const applicantContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewerPage = await reviewerContext.newPage()
      await openCaseAs(reviewerPage, leaseAdmin, reference)
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
      const approveFirst = reviewerPage
        .getByTestId('action-approve_first')
        .getByRole('button', { name: 'Approve first level' })
      await expect(approveFirst).toBeDisabled()
      await expect(reviewerPage.getByTestId('first-approval-blockers')).toBeVisible()

      const company = reviewerPage.getByTestId('doc-row-company_profile')
      await expect(company.getByTestId('doc-expiry-status-company_profile')).toContainText(
        'Valid until',
      )
      await reviewerPage.getByTestId('doc-approve-company_profile').click()
      await expect(reviewerPage.getByTestId('doc-approval-company_profile')).toHaveText('Approved')

      const brand = reviewerPage.getByTestId('doc-row-brand_profile')
      await brand.getByLabel('Remarks (needed to reject)').fill('The logo page is missing')
      await reviewerPage.getByTestId('doc-reject-brand_profile').click()
      await expect(reviewerPage.getByTestId('doc-approval-brand_profile')).toContainText(
        'Rejected: The logo page is missing',
      )
      await expect(approveFirst).toBeDisabled()

      const reupload = reviewerPage.getByTestId('action-request_reupload')
      await expect(reupload.getByTestId('reupload-rejected-hint')).toContainText('Brand Profile')
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
      const uploadCard = applicant.cards('document_upload')
      await expect(uploadCard).toBeVisible({ timeout: 60_000 })
      await expect(uploadCard).toHaveAttribute('data-mode', 'reupload')
      await expect(uploadCard.getByText('The logo page is missing')).toBeVisible()
      await expect(uploadCard.getByText('Company Profile')).toHaveCount(0)
      await applicant.upload('Brand Profile', 'brand_profile.pdf')
      await applicant.resubmitDocuments()
      await expect(applicant.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
        'With the Leasing Admin',
      )

      // The new file is decided again; the company profile keeps its approval.
      await reviewerPage.reload()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
      await expect(reviewerPage.getByTestId('doc-approval-brand_profile')).toHaveText(
        'Waiting for a decision',
      )
      await expect(reviewerPage.getByTestId('doc-approval-company_profile')).toHaveText('Approved')
      await expect(approveFirst).toBeDisabled()
      await reviewerPage.getByTestId('doc-approve-brand_profile').click()
      await expect(reviewerPage.getByTestId('first-approval-blockers')).toHaveCount(0)
      await expect(approveFirst).toBeEnabled()
      await approveFirst.click()
      await expect(reviewerPage.getByTestId('case-stage')).toHaveText('Tenant Qualified')
      await expect(reviewerPage.getByTestId('timeline')).toContainText(
        'Document rejected: brand profile',
      )
    } finally {
      await reviewerContext.close()
      await applicantContext.close()
    }
  })

  test('the final reviewer sees the document decisions read-only', async ({ page, request }) => {
    test.setTimeout(180_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const finalReviewer = await reviewerFor(request, reference, 'final')
    await openCaseAs(page, finalReviewer, reference)
    await expect(page.getByTestId('doc-approval-company_profile')).toHaveText(
      'Waiting for a decision',
    )
    await expect(page.getByTestId('doc-approve-company_profile')).toHaveCount(0)
    await expect(page.getByTestId('action-approve_first')).toHaveCount(0)
  })
})
