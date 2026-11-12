import { expect, test } from '@playwright/test'
import { expectFlowPath, seedFlowCase, mailForCase } from '../../support/flowV2'
import { latestByTemplate } from '../../support/outbox'
import { openCaseAs } from '../../support/stories'

/**
 * S22 Reject Lead (flow v2 §3.6, §3.7, V9; docs/flow-v2/scenarios.json): "Approve Lead?" = No →
 * Reject Lead → "Lead Rejected", the first-approval invitation revoked, the rejection email.
 */
test.describe('S22 Reject Lead @flow-v2 @scripted', () => {
  test('No, reject lead revokes the invitation and says Lead Rejected', async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000)
    const seeded = await seedFlowCase(request, 'qualified')
    const reference = seeded.reference

    await openCaseAs(page, { id: seeded.final_reviewer!, name: '' }, reference)
    await page.getByTestId('assign-unit-ref').fill('G-014')
    await page.getByTestId('assign-unit-submit').click()
    await expect(page.getByTestId('assigned-unit')).toContainText('G-014')

    await page.getByTestId('approve-lead-no').click()
    const reject = page.getByTestId('action-reject')
    await expect(reject.getByLabel('Reason')).toBeFocused()
    await reject.getByLabel('Reason').selectOption('no_space')
    await reject.getByLabel('Remarks for the applicant').fill('No suitable unit this year.')
    await reject.getByRole('button', { name: 'Reject' }).click()
    await expect(page.getByTestId('case-stage')).toHaveText('Lead Rejected')

    const mail = await mailForCase(request, seeded.applicant_email, reference)
    const rejected = latestByTemplate(mail, 'inquiry_rejected')
    expect(rejected?.body).toContain('Lead Rejected')
    expect(latestByTemplate(mail, 'contacts_request')).toBeFalsy()
    expect(latestByTemplate(mail, 'lead_approved')).toBeFalsy()

    await expectFlowPath(
      request,
      reference,
      [
        ['qualified', 'prod2', 'rsm', 'fsd_q', 'approve_lead', 'reject_lead', 'B2'],
        ['reject_lead', 'az2'],
        ['B1', 'rej_mail'],
      ],
      ['req_contacts', 'approve_lead2'],
    )
  })
})
