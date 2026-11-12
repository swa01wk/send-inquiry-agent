import { expect, test } from '@playwright/test'
import { expectFlowPath, reviewerAct, trackingStages } from '../../support/flowV2'
import { fetchDevOutbox, latestByTemplate } from '../../support/outbox'
import { openCaseAs } from '../../support/stories'
import {
  APPLICANT_EMAIL,
  approveDocumentsViaApi,
  reviewerFor,
  submitScriptedInquiry,
} from '../../support/submit'

/**
 * S20 Qualified (flow v2 §3.5, FV2; docs/flow-v2/scenarios.json): Approve Prospective Tenant?
 * = Yes → Primary Tenant Contact Creation (Azure AD invitation) → "Tenant Qualified", with the
 * Regional Sales Manager next. F2: the chart path, and no contacts request until Approve Lead.
 */
test.describe('S20 Qualified @flow-v2 @scripted', () => {
  test('first approval is named Tenant Qualified and invites the primary contact', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(180_000)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    await approveDocumentsViaApi(request, reference)
    const leasingAdmin = await reviewerFor(request, reference, 'first')
    await reviewerAct(request, leasingAdmin.id, reference, 'approve_first')

    const finalReviewer = await reviewerFor(request, reference, 'final')
    const context = await browser.newContext()
    try {
      const consolePage = await context.newPage()
      await openCaseAs(consolePage, finalReviewer, reference)
      await expect(consolePage.getByTestId('case-stage')).toHaveText('Tenant Qualified')
      // The case summary's queue by its chart name: s1-happy-path is a Specialty unit, so the
      // Regional Product Line Manager (a Store or Office unit: Regional Sales Manager).
      await expect(
        consolePage.getByText(/Regional (Sales Manager|Product Line Manager \(\w+\)) · /),
      ).toBeVisible()
      await expect(consolePage.getByTestId('action-remove_contact')).toHaveCount(0)
    } finally {
      await context.close()
    }

    const mail = await fetchDevOutbox(request, APPLICANT_EMAIL)
    expect(latestByTemplate(mail, 'azure_ad_invitation')).toBeTruthy()
    expect(latestByTemplate(mail, 'first_level_approved')?.subject).toContain('Tenant Qualified')

    const tracking = latestByTemplate(mail, 'submission_email')?.links.find((l) =>
      l.includes('/inquiry/status/'),
    )
    const stages = await trackingStages(request, tracking!)
    expect(stages.map((s) => s.label)).toEqual([
      'Inquiry submitted',
      'With the Leasing Admin',
      'Tenant Qualified',
      'Outcome',
    ])
    expect(stages.find((s) => s.key === 'second_review')?.state).toBe('current')

    // F2 (§3.7): the contacts wait for "Approve Lead?" = Yes.
    expect(latestByTemplate(mail, 'contacts_request')).toBeFalsy()
    await expectFlowPath(request, reference, [
      ['complete1', 'vla', 'docsok', 'approve_pt', 'ptc_create', 'qualified'],
      ['ptc_create', 'az1'],
      ['ptc_create', 'reg_link1', 'reg1'],
    ])
  })
})
