import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import {
  advanceClock,
  attentionFor,
  expectFlowPath,
  seedFlowCase,
  tenantSendsSalesData,
} from '../../support/flowV2'
import { fetchDevOutbox, latestByTemplate } from '../../support/outbox'
import { openCaseAs } from '../../support/stories'

const FILE = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../fixtures/files/company_profile.pdf',
)

/**
 * S21 Forecasted Sales Data, then Approve Lead (flow v2 §3.7, V6, V11, E4;
 * docs/flow-v2/scenarios.json): the Regional Sales Manager assigns the unit, asks for
 * Forecasted Sales Data (Approve Lead? waits), a reminder is drafted after 72 h, the tenant
 * sends it, and "Yes, approve lead" moves the case to "Lead Approved".
 */
test.describe('S21 Forecasted Sales Data @flow-v2 @scripted', () => {
  test('unit, Forecasted Sales Data, reminder, then Yes, approve lead', async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000)
    const seeded = await seedFlowCase(request, 'qualified', { unit_type: 'store' })
    const reference = seeded.reference
    const rsm = { id: seeded.final_reviewer!, name: '' }

    await openCaseAs(page, rsm, reference)
    await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
    await expect(page.getByTestId('lead-approval-blockers')).toContainText('Assign the unit first')
    await page.getByTestId('assign-unit-ref').fill('G-014')
    await page.getByTestId('assign-unit-area').fill('95')
    await page.getByTestId('assign-unit-submit').click()
    await expect(page.getByTestId('assigned-unit')).toContainText('G-014')

    const requests = page.getByTestId('action-requests')
    await requests.getByLabel('Note for the applicant (optional)').fill('Monthly, first year.')
    await requests.getByRole('button', { name: 'Request Forecasted Sales Data' }).click()
    await expect(page.getByTestId('lead-approval-blockers')).toContainText(
      'Forecasted Sales Data not received yet',
    )
    await expect(page.getByTestId('action-approve_lead')).toHaveCount(0)

    // E4: a reminder is drafted once the request is 72 h old.
    await advanceClock(request, 73)
    const reminders = (await attentionFor(request, rsm.id)).filter(
      (i) => i.trigger === 'applicant_reminder' && i.reference === reference,
    )
    expect(reminders).toHaveLength(1)
    expect(reminders[0].text).toContain('Forecasted Sales Data')

    const mail = latestByTemplate(
      await fetchDevOutbox(request, seeded.applicant_email),
      'sales_data_request',
    )
    const link = mail?.links.find((l) => l.includes('/inquiry/case'))
    expect(link).toBeTruthy()
    await tenantSendsSalesData(request, link!, {
      name: 'forecast.pdf',
      buffer: readFileSync(FILE),
    })

    await page.reload()
    await expect(page.getByTestId('lead-approval-blockers')).toHaveCount(0)
    await page.getByTestId('approve-lead-yes').click()
    await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
    await expect(page.getByTestId('approve-lead-final')).toBeDisabled()

    await expectFlowPath(request, reference, [
      ['qualified', 'prod2', 'rsm', 'fsd_q', 'fsd_notify', 'fsd_provide', 'approve_lead'],
    ])
  })
})
