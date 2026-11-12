import { expect, test } from '@playwright/test'
import { reviewerAct, trackingStages } from '../../support/flowV2'
import { fetchDevOutbox, latestByTemplate } from '../../support/outbox'
import { openCaseAs } from '../../support/stories'
import {
  APPLICANT_EMAIL,
  approveDocumentsViaApi,
  reviewerFor,
  submitScriptedInquiry,
} from '../../support/submit'

/**
 * S19 Not qualified (flow v2 §3.5, FV2; docs/flow-v2/scenarios.json): Approve Prospective
 * Tenant? = No → "Tenant Not Qualified" → rejection email, and no Azure AD invitation.
 * F1 checks the chart names and the outbox; `expectFlowPath` joins on F2.
 */
test.describe('S19 Not qualified @flow-v2 @scripted', () => {
  test('first-level rejection is named Tenant Not Qualified', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(180_000)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    await approveDocumentsViaApi(request, reference)
    const leasingAdmin = await reviewerFor(request, reference, 'first')
    await reviewerAct(request, leasingAdmin.id, reference, 'reject', {
      remarks: 'Not a fit for this mall',
      reason_category: 'not_a_fit',
    })

    const context = await browser.newContext()
    try {
      const consolePage = await context.newPage()
      await openCaseAs(consolePage, leasingAdmin, reference)
      await expect(consolePage.getByTestId('case-stage')).toHaveText('Tenant Not Qualified')
    } finally {
      await context.close()
    }

    const mail = await fetchDevOutbox(request, APPLICANT_EMAIL)
    const rejection = latestByTemplate(mail, 'inquiry_rejected')
    expect(rejection?.body).toContain('Outcome: Tenant Not Qualified')
    expect(mail.filter((m) => m.template === 'azure_ad_invitation')).toHaveLength(0)

    const tracking = latestByTemplate(mail, 'submission_email')?.links.find((l) =>
      l.includes('/inquiry/status/'),
    )
    expect(tracking).toBeTruthy()
    const stages = await trackingStages(request, tracking!)
    expect(stages.at(-1)).toEqual({
      key: 'outcome',
      label: 'Outcome — Tenant Not Qualified',
      state: 'done',
    })
  })
})
