import { expect, test } from '@playwright/test'
import { expectFlowPath, seedFlowCase } from '../../support/flowV2'
import { fetchDevOutbox, latestByTemplate } from '../../support/outbox'
import { InquiryPage } from '../../pages/inquiry'
import { openCaseAs } from '../../support/stories'

/**
 * S23 Approve Lead → contacts → Approve Lead → Yardi (flow v2 §3.7, V6, V7, V11, E3;
 * docs/flow-v2/scenarios.json): Yes opens the contacts; the final Approve Lead is disabled
 * until the Authorized Signatory and Billing Contact are in; then accounts and Yardi.
 */
test.describe('S23 Approve Lead to Yardi @flow-v2 @scripted', () => {
  test('Yes → contacts → the final Approve Lead → Yardi', async ({ page, browser, request }) => {
    test.setTimeout(240_000)
    const seeded = await seedFlowCase(request, 'qualified')
    const reference = seeded.reference

    await openCaseAs(page, { id: seeded.final_reviewer!, name: '' }, reference)
    await page.getByTestId('assign-unit-ref').fill('G-014')
    await page.getByTestId('assign-unit-area').fill('95')
    await page.getByTestId('assign-unit-submit').click()
    await expect(page.getByTestId('assigned-unit')).toContainText('G-014')
    await page.getByTestId('approve-lead-yes').click()
    await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
    await expect(page.getByTestId('approve-lead-final')).toBeDisabled()
    await expect(page.getByTestId('approval-blockers')).toContainText('Contacts request still open')
    await expect(page.getByTestId('action-reject')).toHaveCount(0)

    const outbox = await fetchDevOutbox(request, seeded.applicant_email)
    expect(latestByTemplate(outbox, 'lead_approved')?.subject).toContain('Lead Approved')
    const link = latestByTemplate(outbox, 'contacts_request')?.links.find((l) =>
      l.includes('/inquiry/case'),
    )
    expect(link).toBeTruthy()
    const caseUrl = new URL(link!)
    caseUrl.searchParams.set('e2eCaseScenario', 't1-contacts')

    const applicantContext = await browser.newContext()
    try {
      const applicantPage = await applicantContext.newPage()
      const applicant = new InquiryPage(applicantPage)
      await applicantPage.goto(caseUrl.toString())
      await applicant.waitForChatReady()
      await expect(applicant.cards('case_status')).toBeVisible({ timeout: 60_000 })
      await applicant.say(
        "I'm the signatory; billing is Omar Saleh, omar@beanstreet.example, +966551234567",
      )
      await expect(applicant.cards('contacts')).toBeVisible({ timeout: 60_000 })
      await applicant.submitContacts()
    } finally {
      await applicantContext.close()
    }

    await page.reload()
    await expect(page.getByTestId('approval-blockers')).toHaveCount(0)
    await expect(page.getByTestId('approve-lead-final')).toBeEnabled()
    await page.getByTestId('approve-lead-final').click()
    await expect(page.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
    await expect
      .poll(async () =>
        latestByTemplate(await fetchDevOutbox(request, 'omar@beanstreet.example'), 'azure_ad_invitation'),
      )
      .toBeTruthy()

    await expectFlowPath(request, reference, [
      [
        'qualified',
        'prod2',
        'rsm',
        'fsd_q',
        'approve_lead',
        'req_contacts',
        'contacts_notify',
        'contacts_provide',
        'approve_lead2',
        'create_all',
        'yardi_box',
        'end',
      ],
      ['create_all', 'az3', 'reg_link2', 'reg2'],
    ])
  })
})
