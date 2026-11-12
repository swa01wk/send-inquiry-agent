import { expect, test } from '@playwright/test'
import { clearDevOutbox } from '../support/outbox'
import { openCaseAs } from '../support/stories'
import { approveDocumentsViaApi, reviewerFor, submitScriptedInquiry } from '../support/submit'

/** Day 4: the console offers only the actions the state machine allows (L4 §3.3). */
test.describe('Reviewer console @scripted', () => {
  test('first review → approve first level → second review shows only its legal actions', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)
    const reference = await submitScriptedInquiry(page, request, 's1-happy-path')
    const reviewer = await reviewerFor(request, reference)

    await page.goto('/review')
    await page.getByLabel('Reviewer').selectOption(reviewer.id)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByTestId('signed-in-reviewer')).toContainText(reviewer.name)
    await page.getByTestId(`queue-row-${reference}`).getByRole('link', { name: reference }).click()

    // First review, Lease Admin: decide the first level, ask for a re-upload or reject.
    await expect(page.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
    await expect(page.getByTestId('action-approve_first')).toBeVisible()
    await expect(page.getByTestId('action-request_reupload')).toBeVisible()
    await expect(page.getByTestId('action-reject')).toBeVisible()
    await expect(page.getByTestId('action-approve')).toHaveCount(0)
    await expect(page.getByTestId('action-yardi')).toHaveCount(0)
    await expect(page.getByTestId('action-requests')).toHaveCount(0)

    // Day R2: approval waits until each document is approved (demo feedback §3.4).
    await expect(page.getByTestId('first-approval-blockers')).toBeVisible()
    await expect(
      page.getByTestId('action-approve_first').getByRole('button', { name: 'Approve first level' }),
    ).toBeDisabled()
    await approveDocumentsViaApi(request, reference)
    await page.reload()
    await expect(page.getByTestId('first-approval-blockers')).toHaveCount(0)

    await page
      .getByTestId('action-approve_first')
      .getByRole('button', { name: 'Approve first level' })
      .click()

    // Second review is the final level: the Lease Admin has no actions there.
    await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
    await expect(page.getByTestId('action-approve_first')).toHaveCount(0)
    await expect(page.getByTestId('action-yardi')).toHaveCount(0)

    // The Regional Sales Manager takes over (demo feedback §3.2). Flow v2 (§3.7): no
    // contacts request yet; "Approve Lead?" waits for the unit.
    const finalReviewer = await reviewerFor(request, reference, 'final')
    await openCaseAs(page, finalReviewer, reference)
    await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
    await expect(page.getByTestId('action-approve_first')).toHaveCount(0)
    await expect(page.getByTestId('action-approve')).toHaveCount(0)
    await expect(page.getByTestId('action-approve_lead')).toHaveCount(0)
    await expect(page.getByTestId('lead-approval-blockers')).toContainText('Assign the unit first')
    await expect(page.getByTestId('action-yardi')).toBeVisible()
    const requests = page.getByTestId('action-requests')
    await expect(
      requests.getByRole('button', { name: 'Request Forecasted Sales Data' }),
    ).toBeVisible()
    await expect(requests.getByRole('button', { name: 'Request contacts' })).toHaveCount(0)
    await expect(page.getByTestId('timeline')).toContainText(/approved/i)

    // Assign the unit: "Approve Lead?" opens.
    await page.getByTestId('assign-unit-ref').fill('G-014')
    await page.getByTestId('assign-unit-area').fill('95')
    await page.getByTestId('assign-unit-submit').click()
    await expect(page.getByTestId('assigned-unit')).toContainText('G-014')
    await expect(page.getByTestId('lead-approval-blockers')).toHaveCount(0)
    await page.getByTestId('approve-lead-yes').click()
    await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
    await expect(page.getByTestId('approve-lead-final')).toBeDisabled()
    await expect(page.getByTestId('approval-blockers')).toContainText('Contacts request still open')
    await expect(page.getByTestId('requests')).toContainText('contacts · open')
    await expect(page.getByTestId('action-reject')).toHaveCount(0)

    // Back on the queue, the case now waits on the applicant.
    await page.getByRole('link', { name: '← Back to the queue' }).click()
    await expect(page.getByTestId(`queue-row-${reference}`)).toContainText('Applicant')
  })
})
