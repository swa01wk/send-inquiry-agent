import { expect, test } from '@playwright/test'
import { expectFlowPath, seedFlowCase } from '../../support/flowV2'
import { fetchDevOutbox, latestByTemplate } from '../../support/outbox'
import { InquiryPage } from '../../pages/inquiry'
import { openCaseAs } from '../../support/stories'

/**
 * S18 A document is rejected (flow v2 V14; docs/flow-v2/scenarios.json): the Leasing Admin
 * rejects the Brand Profile with a remark and asks for it again; the tenant asks the case chat
 * what's needed (only that document and the remark), re-uploads and resubmits; the new file
 * needs a decision again, both profiles are approved, and the first level goes through.
 */
test.describe('S18 A document is rejected @flow-v2 @scripted', () => {
  test('reject, re-upload from the case chat, approve again', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(180_000)
    const seeded = await seedFlowCase(request, 'submitted', {
      unit_type: 'store',
      malls: ['riyadh-mall-a'],
    })
    const reference = seeded.reference
    const leasingAdmin = { id: seeded.first_reviewer!, name: '' }

    await openCaseAs(page, leasingAdmin, reference)
    await expect(page.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
    await page
      .getByTestId('doc-row-brand_profile')
      .getByLabel('Remarks (needed to reject)')
      .fill('Logo page missing')
    await page.getByTestId('doc-reject-brand_profile').click()
    await expect(page.getByTestId('doc-approval-brand_profile')).toContainText(
      'Rejected: Logo page missing',
    )
    await page
      .getByTestId('action-request_reupload')
      .getByRole('button', { name: 'Request re-upload' })
      .click()
    await expect(page.getByTestId('case-stage')).toContainText('waiting for re-upload')

    await expect
      .poll(async () =>
        latestByTemplate(
          (await fetchDevOutbox(request, seeded.applicant_email)).filter(
            (m) => m.inquiry_id === reference,
          ),
          'reupload_request',
        ),
      )
      .toBeTruthy()
    const mail = latestByTemplate(
      (await fetchDevOutbox(request, seeded.applicant_email)).filter(
        (m) => m.inquiry_id === reference,
      ),
      'reupload_request',
    )!
    const link = mail.links.find((l) => l.includes('/inquiry/case'))
    expect(link, 'case link in reupload_request').toBeTruthy()
    const caseUrl = new URL(link!)
    caseUrl.searchParams.set('e2eCaseScenario', 'flow-v2-s18')

    const viewport = page.viewportSize()
    const applicantContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const applicant = new InquiryPage(await applicantContext.newPage())
      await applicant.page.goto(caseUrl.toString())
      await applicant.waitForChatReady()
      const uploadCard = applicant.cards('document_upload')
      await expect(uploadCard).toBeVisible({ timeout: 60_000 })
      await expect(uploadCard).toHaveAttribute('data-mode', 'reupload')
      await expect(uploadCard.getByText('Logo page missing')).toBeVisible()
      await expect(uploadCard.getByText('Company Profile')).toHaveCount(0)

      await applicant.say('what do you need from me?')
      const reply = await applicant.lastReply()
      expect(reply).toMatch(/Brand Profile/)
      expect(reply).toMatch(/logo page/i)
      expect(reply).not.toMatch(/Company Profile/)

      await applicant.upload('Brand Profile', 'brand_profile.pdf')
      await applicant.resubmitDocuments()
      await expect(applicant.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
        'With the Leasing Admin',
      )
    } finally {
      await applicantContext.close()
    }

    await page.reload()
    await expect(page.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
    await expect(page.getByTestId('doc-approval-brand_profile')).toHaveText(
      'Waiting for a decision',
    )
    await page.getByTestId('doc-approve-brand_profile').click()
    await expect(page.getByTestId('doc-approval-brand_profile')).toHaveText('Approved')
    if ((await page.getByTestId('doc-approve-company_profile').count()) > 0) {
      await page.getByTestId('doc-approve-company_profile').click()
    }
    await expect(page.getByTestId('doc-approval-company_profile')).toHaveText('Approved')
    await expect(page.getByTestId('first-approval-blockers')).toHaveCount(0)

    const sent = (await fetchDevOutbox(request))
      .filter((m) => m.inquiry_id === reference)
      .map((m) => m.template)
    expect(sent).toContain('reupload_request')
    expect(sent).toContain('reupload_received')
    // The case waits at first review (catalogue `expect`); the chart's second Docs OK? is
    // recorded when the Leasing Admin approves the first level.
    await expectFlowPath(request, reference, [
      ['complete1', 'vla', 'docsok', 'reup_req', 'reup_mail', 'reup_submit'],
    ])
    await page
      .getByTestId('action-approve_first')
      .getByRole('button', { name: 'Approve first level' })
      .click()
    await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
    await expectFlowPath(request, reference, [
      ['complete1', 'vla', 'docsok', 'reup_req', 'reup_mail', 'reup_submit', 'docsok'],
    ])
  })
})
