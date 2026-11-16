import { expect, test, type Page } from '@playwright/test'
import { InquiryPage } from '../../pages/inquiry'
import {
  BOTH,
  LIVE,
  LIVE_ONLY,
  REVIEWERS,
  SARA,
  Tester,
  approveDocument,
  approveFirstLevel,
  assignUnit,
  devClock,
  inboxLink,
  inboxMessage,
  openCaseChatFromEmail,
  rejectWith,
  saysLive,
  seedCase,
  type Seeded,
} from '../../support/qa'

/**
 * docs/scenario-queries.md, "After submit (S18–S24)": the reviewer in the console, the
 * applicant in the case chat opened from Sara's email in /dev/inbox. Each scenario starts
 * from a seeded case (the doc's seed helper); the doc's chain on one inquiry
 * (S18 → S20 → S21 → S23) runs live at the end of this file.
 */
const TIMEOUT = LIVE ? 600_000 : 240_000
const REVIEWER_NAMES = new RegExp(
  Object.values(REVIEWERS)
    .map((r) => r.name)
    .join('|'),
)

async function reviewerWindow(t: Tester, reviewerId: string, reference: string): Promise<Page> {
  const page = await t.window()
  await page.goto(
    `/review/cases/${encodeURIComponent(reference)}?as=${encodeURIComponent(reviewerId)}`,
  )
  await expect(page.getByTestId('case-stage')).toBeVisible()
  return page
}

/** Doc S18 row 1: the Leasing Admin opens the case from "Inquiry for approval" in /dev/inbox. */
async function leasingAdminFromEmail(t: Tester, seeded: Seeded): Promise<Page> {
  const page = await t.window()
  const path = await inboxLink(page, {
    to: REVIEWERS.reem.email,
    template: 'review_assigned',
    reference: seeded.reference,
    contains: '/review/cases/',
  })
  await page.goto(path)
  await expect(page.getByTestId('case-stage')).toHaveText('With the Leasing Admin')
  return page
}

async function neverNamesReviewer(chat: InquiryPage): Promise<void> {
  for (const reply of await chat.allReplies()) expect(reply).not.toMatch(REVIEWER_NAMES)
}

test.describe('Scenario queries: after submit', () => {
  test.beforeEach(() => test.setTimeout(TIMEOUT))

  test(`S18 A document is rejected ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S18')
    try {
      const seeded = await seedCase(request, {
        stage: 'submitted',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      let admin!: Page
      await t.row('1 Leasing Admin: Inquiry for approval → open the case', [], async () => {
        admin = await leasingAdminFromEmail(t, seeded)
        await expect(admin.getByText(/Valid until/).first()).toBeVisible()
        await expect(admin.getByTestId('first-approval-blockers')).toBeVisible()
      })
      await t.row(
        '2 Approve the Company Profile; reject the Brand Profile → Request re-upload',
        [],
        async () => {
          await approveDocument(admin, 'company_profile')
          await admin
            .getByTestId('doc-row-brand_profile')
            .getByLabel('Remarks (needed to reject)')
            .fill('Logo page missing')
          await admin.getByTestId('doc-reject-brand_profile').click()
          await expect(admin.getByTestId('doc-approval-brand_profile')).toContainText(
            'Rejected: Logo page missing',
          )
          await admin
            .getByTestId('action-request_reupload')
            .getByRole('button', { name: 'Request re-upload' })
            .click()
          await expect(admin.getByTestId('case-stage')).toContainText('waiting for re-upload')
        },
      )
      let applicant!: InquiryPage
      await t.row('3 Applicant: reupload_request → case link', [], async () => {
        applicant = await openCaseChatFromEmail(t, {
          to: seeded.applicant_email,
          template: 'reupload_request',
          reference: seeded.reference,
          script: 'flow-v2-s18',
        })
        const card = applicant.cards('document_upload')
        await expect(card).toBeVisible({ timeout: 60_000 })
        await expect(card).toHaveAttribute('data-mode', 'reupload')
        await expect(card.getByText('Logo page missing')).toBeVisible()
        await expect(card.getByText('Company Profile')).toHaveCount(0)
      })
      await t.row('4 what do you need from me?', [], async () => {
        await applicant.say('what do you need from me?')
        const reply = await applicant.lastReply()
        expect(reply).toMatch(/Brand Profile/)
        expect(reply).toMatch(/logo page/i)
        // Live run 16 Nov: one reply said the outcome was "Tenant Qualified" while the case
        // waited for the re-upload. The status card lists that stage as a future one.
        expect(reply, 'names only the current stage').not.toMatch(/Tenant Qualified/i)
        expect(reply).not.toMatch(/Company Profile/)
        await neverNamesReviewer(applicant)
      })
      await t.row('5 Upload brand_profile.pdf → Resubmit', [], async () => {
        await applicant.upload('Brand Profile', 'brand_profile.pdf')
        await applicant.resubmitDocuments()
        await expect(applicant.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
          'With the Leasing Admin',
        )
      })
      await t.row('6 Leasing Admin: reload; approve the Brand Profile', [], async () => {
        await admin.reload()
        await expect(admin.getByTestId('doc-approval-brand_profile')).toHaveText(
          'Waiting for a decision',
        )
        await expect(admin.getByTestId('doc-approval-company_profile')).toHaveText('Approved')
        await approveDocument(admin, 'brand_profile')
        await expect(admin.getByTestId('first-approval-blockers')).toHaveCount(0)
      })
    } finally {
      await t.close()
    }
  })

  test(`S19 Not qualified ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S19')
    try {
      const seeded = await seedCase(request, {
        stage: 'submitted',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      await t.row('1 Leasing Admin: approve both documents → Reject, Not a fit', [], async () => {
        const admin = await leasingAdminFromEmail(t, seeded)
        await approveDocument(admin, 'company_profile')
        await approveDocument(admin, 'brand_profile')
        await rejectWith(admin, 'not_a_fit', 'Not a fit for this mall')
        await expect(admin.getByTestId('case-stage')).toHaveText('Tenant Not Qualified')
      })
      await t.row(
        '2 Applicant: inquiry_rejected → case link → why was it rejected?',
        [],
        async () => {
          const applicant = await openCaseChatFromEmail(t, {
            to: seeded.applicant_email,
            template: 'inquiry_rejected',
            reference: seeded.reference,
            script: 'flow-v2-s19',
          })
          await applicant.say('why was it rejected?')
          const reply = await applicant.lastReply()
          expect(reply).toMatch(/Tenant Not Qualified|not (a )?(good )?fit/i)
          expect(reply).toMatch(/new inquiry/i)
          expect(reply).not.toMatch(/\b(guarantee|will be approved)\b/i)
          await neverNamesReviewer(applicant)
        },
      )
    } finally {
      await t.close()
    }
  })

  test(`S20 Qualified ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S20')
    try {
      const seeded = await seedCase(request, {
        stage: 'submitted',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      await t.row('1 Leasing Admin: Approve first level', [], async () => {
        const admin = await leasingAdminFromEmail(t, seeded)
        await approveFirstLevel(admin)
      })
      await t.row(
        '2 /dev/inbox: first_level_approved and a Tenant Central invitation',
        [],
        async () => {
          const inbox = await t.window()
          await inboxMessage(inbox, {
            to: seeded.applicant_email,
            template: 'first_level_approved',
            reference: seeded.reference,
          })
          await inboxMessage(inbox, { to: seeded.applicant_email, template: 'azure_ad_invitation' })
        },
      )
      await t.row('3 Applicant: case link → where is my inquiry?', [], async () => {
        const applicant = await openCaseChatFromEmail(t, {
          to: seeded.applicant_email,
          template: 'first_level_approved',
          reference: seeded.reference,
          script: 'flow-v2-s20',
        })
        await applicant.say('where is my inquiry?')
        const reply = await applicant.lastReply()
        expect(reply).toMatch(/Tenant Qualified|Regional Sales Manager/i)
      })
    } finally {
      await t.close()
    }
  })

  test(`S21 Forecasted sales data asked for ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S21')
    try {
      const seeded = await seedCase(request, {
        stage: 'qualified',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      const rsm = await reviewerWindow(t, seeded.final_reviewer!, seeded.reference)
      await t.row('1 RSM: open the case', [], async () => {
        await expect(rsm.getByTestId('case-stage')).toHaveText('Tenant Qualified')
        await expect(rsm.getByTestId('lead-approval-blockers')).toContainText(
          'Assign the unit first',
        )
      })
      if (LIVE) {
        await t.row('2 Reviewer assistant: should I ask for forecasted sales?', [], async () => {
          const panel = rsm.getByTestId('reviewer-assistant-panel')
          await panel.getByLabel('Message').fill('should I ask for forecasted sales?')
          await panel.getByRole('button', { name: 'Send' }).click()
          const reply = panel.getByTestId('assistant-reply').last()
          await expect(reply).toHaveText(/.{20,}/s, { timeout: 120_000 })
          // E2: a suggestion with its reason; it never sends the request itself.
          await expect(rsm.getByTestId('lead-approval-blockers')).toContainText(
            'Assign the unit first',
          )
        })
      }
      await t.row('3 Assign the unit: Riyadh Mall A, RMA-G-014, 45', [], () => assignUnit(rsm))
      await t.row('4 Request Forecasted Sales Data', [], async () => {
        const requests = rsm.getByTestId('action-requests')
        await requests
          .getByLabel('Note for the applicant (optional)')
          .fill('Please share 12-month forecasted sales')
        await requests.getByRole('button', { name: 'Request Forecasted Sales Data' }).click()
        await expect(rsm.getByTestId('lead-approval-blockers')).toContainText(
          'Forecasted Sales Data not received yet',
        )
      })
      await t.row(
        '5 /dev +24 h, then +48 h → Needs attention has a drafted reminder',
        [],
        async () => {
          const dev = await t.window()
          await devClock(dev, '+24 h')
          await devClock(dev, '+48 h')
          await rsm.goto('/review/attention')
          const item = rsm.getByTestId(`attention-applicant_reminder-${seeded.reference}`)
          await expect(item).toBeVisible()
          await expect(item).toContainText('Forecasted Sales Data')
        },
      )
      await t.row('6 Applicant: sales_data_request → here it is → upload → Send', [], async () => {
        const applicant = await openCaseChatFromEmail(t, {
          to: seeded.applicant_email,
          template: 'sales_data_request',
          reference: seeded.reference,
          script: 'flow-v2-s21',
        })
        await applicant.say('here it is')
        await expect(applicant.page.getByTestId('sales-data-upload-card')).toBeVisible({
          timeout: 60_000,
        })
        await applicant.uploadForecastedSalesData('company_profile.pdf')
        await applicant.submitForecastedSalesData()
        await saysLive(
          applicant,
          /Forecasted Sales Data/i,
          'the reply says "Forecasted Sales Data"',
        )
      })
      await t.row('7 RSM: reload → Yes, approve lead', [], async () => {
        await rsm.goto(
          `/review/cases/${seeded.reference}?as=${encodeURIComponent(seeded.final_reviewer!)}`,
        )
        await expect(rsm.getByTestId('lead-approval-blockers')).toHaveCount(0)
        await rsm.getByTestId('approve-lead-yes').click()
        await expect(rsm.getByTestId('case-stage')).toHaveText('Lead Approved')
        await expect(rsm.getByTestId('approve-lead-final')).toBeDisabled()
      })
    } finally {
      await t.close()
    }
  })

  test(`S22 Lead rejected ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S22')
    try {
      const seeded = await seedCase(request, {
        stage: 'qualified',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      await t.row('1 RSM: assign the unit → No, reject lead → No space', [], async () => {
        const rsm = await reviewerWindow(t, seeded.final_reviewer!, seeded.reference)
        await assignUnit(rsm)
        await rsm.getByTestId('approve-lead-no').click()
        await rejectWith(rsm, 'no_space', 'No space in the requested size')
        await expect(rsm.getByTestId('case-stage')).toHaveText('Lead Rejected')
      })
      await t.row('2 Applicant: inquiry_rejected → case link → what happened?', [], async () => {
        const applicant = await openCaseChatFromEmail(t, {
          to: seeded.applicant_email,
          template: 'inquiry_rejected',
          reference: seeded.reference,
          script: 'flow-v2-s22',
        })
        await applicant.say('what happened?')
        const reply = await applicant.lastReply()
        expect(reply).toMatch(/Lead Rejected|rejected|no (suitable )?(unit|space)/i)
        expect(reply).toMatch(/new inquiry/i)
        await neverNamesReviewer(applicant)
      })
    } finally {
      await t.close()
    }
  })

  test(`S23 Lead approved, contacts, final approval ${BOTH}`, async ({
    page,
    browser,
    request,
  }) => {
    const t = await Tester.blank(page, browser, request, 'S23')
    try {
      const seeded = await seedCase(request, {
        stage: 'qualified',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      const rsm = await reviewerWindow(t, seeded.final_reviewer!, seeded.reference)
      await t.row('0 RSM: assign the unit → Yes, approve lead', [], async () => {
        await assignUnit(rsm)
        await rsm.getByTestId('approve-lead-yes').click()
        await expect(rsm.getByTestId('case-stage')).toHaveText('Lead Approved')
        await expect(rsm.getByTestId('approve-lead-final')).toBeDisabled()
      })
      let applicant!: InquiryPage
      await t.row(
        '1 Applicant: contacts_request → case link: the signatory question first',
        [],
        async () => {
          applicant = await openCaseChatFromEmail(t, {
            to: seeded.applicant_email,
            template: 'contacts_request',
            reference: seeded.reference,
            script: 'qa-s23',
          })
          await expect(applicant.cards('signatory_question')).toContainText(
            'Are you the authorised signatory for your company?',
            { timeout: 60_000 },
          )
        },
      )
      await t.row('2 No, someone else is', [], async () => {
        await applicant.answerSignatoryQuestion(false)
        await expect(applicant.cards('signatory_question')).toContainText('No, someone else is')
      })
      await t.row('3 Ahmed Saleh signs, ahmed@beanstreet.example, 0507654321', [], async () => {
        await applicant.say('Ahmed Saleh signs, ahmed@beanstreet.example, 0507654321')
        // The card refreshes on show_contacts_review (once both roles are in), not on every
        // update_contacts, so live runs read the reply here; scripted runs show the card.
        if (LIVE) {
          await saysLive(applicant, /Ahmed/, 'the signatory is saved')
        } else {
          await expect(
            applicant.cards('contacts').last().getByTestId('contact-row-authorized_signatory'),
          ).toContainText('Ahmed', { timeout: 60_000 })
        }
        await saysLive(applicant, /billing/i, 'asks for the billing contact')
      })
      await t.row(
        '4 RSM: reload → the final Approve Lead is disabled: Billing Contact missing',
        [],
        async () => {
          await rsm.reload()
          await expect(rsm.getByTestId('approve-lead-final')).toBeDisabled()
          await expect(rsm.getByTestId('approval-blockers')).toContainText(
            'Billing Contact still needed',
          )
        },
      )
      await t.row(
        '5 billing is Nora Ali, nora@beanstreet.example, 0509998877 → Send contacts',
        [],
        async () => {
          await applicant.say('billing is Nora Ali, nora@beanstreet.example, 0509998877')
          const contacts = applicant.cards('contacts').last()
          await expect(
            contacts.getByTestId('contact-row-billing_contact'),
            `last reply: ${await applicant.lastReply()}`,
          ).toContainText('Nora', { timeout: 60_000 })
          await expect(contacts.getByTestId('contact-row-authorized_signatory')).toContainText(
            'Ahmed',
          )
          await applicant.submitContacts()
          for (const reply of await applicant.allReplies())
            expect(reply).not.toMatch(/approve (each|every|this) contact/i)
        },
      )
      await t.row('6 RSM: reload → Approve Lead → Approved and sent to Yardi', [], async () => {
        await rsm.reload()
        await expect(rsm.getByTestId('approval-blockers')).toHaveCount(0)
        await rsm.getByTestId('approve-lead-final').click()
        await expect(rsm.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
      })
      await t.row(
        '7 /dev/inbox: inquiry_accepted, and invitations for the new contacts',
        [],
        async () => {
          const inbox = await t.window()
          await inboxMessage(inbox, {
            to: seeded.applicant_email,
            template: 'inquiry_accepted',
            reference: seeded.reference,
          })
          await inboxMessage(inbox, {
            to: 'ahmed@beanstreet.example',
            template: 'azure_ad_invitation',
          })
          await inboxMessage(inbox, {
            to: 'nora@beanstreet.example',
            template: 'azure_ad_invitation',
          })
        },
      )
    } finally {
      await t.close()
    }
  })

  test(`S24 Applicant is the signatory ${BOTH}`, async ({ page, browser, request }) => {
    const t = await Tester.blank(page, browser, request, 'S24')
    try {
      const seeded = await seedCase(request, {
        stage: 'lead_approved',
        unit_type: 'store',
        malls: ['riyadh-mall-a'],
      })
      let applicant!: InquiryPage
      await t.row(
        '1 Applicant: contacts_request → case link: the signatory question first',
        [],
        async () => {
          applicant = await openCaseChatFromEmail(t, {
            to: seeded.applicant_email,
            template: 'contacts_request',
            reference: seeded.reference,
            script: 'qa-s24',
          })
          await expect(applicant.cards('signatory_question')).toBeVisible({ timeout: 60_000 })
        },
      )
      await t.row("2 Yes, I'm the authorised signatory", [], async () => {
        await applicant.answerSignatoryQuestion(true)
        await expect(
          applicant.cards('contacts').last().getByText('Same as primary contact'),
        ).toBeVisible({
          timeout: 60_000,
        })
      })
      await t.row(
        '3 billing is Nora Ali, nora@beanstreet.example, 0509998877 → Send contacts',
        [],
        async () => {
          await applicant.say('billing is Nora Ali, nora@beanstreet.example, 0509998877')
          const contacts = applicant.cards('contacts').last()
          await expect(contacts.getByTestId('contact-row-billing_contact')).toContainText('Nora', {
            timeout: 60_000,
          })
          await applicant.submitContacts()
        },
      )
      await t.row('4 RSM: Approve Lead → Approved and sent to Yardi', [], async () => {
        const rsm = await reviewerWindow(t, seeded.final_reviewer!, seeded.reference)
        await expect(rsm.getByTestId('case-stage')).toHaveText('Lead Approved')
        await rsm.getByTestId('approve-lead-final').click()
        await expect(rsm.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
      })
    } finally {
      await t.close()
    }
  })

  test(`S24 variations: partner signs, not sure ${LIVE_ONLY}`, async ({
    page,
    browser,
    request,
  }) => {
    test.skip(!LIVE, 'live only: unscripted answers')
    const t = await Tester.blank(page, browser, request, 'S24')
    try {
      for (const [answer, pattern, why] of [
        [
          'not sure, my partner Ahmed signs',
          /Ahmed|email|details|contact/i,
          "asks for Ahmed's details",
        ],
        ["I'm not sure", /signatory|sign/i, 'explains what a signatory is, without guessing'],
      ] as const) {
        const seeded = await seedCase(request, { stage: 'lead_approved' })
        await t.row(answer, [], async () => {
          const applicant = await openCaseChatFromEmail(t, {
            to: seeded.applicant_email,
            template: 'contacts_request',
            reference: seeded.reference,
            script: 'qa-s24',
          })
          await expect(applicant.cards('signatory_question')).toBeVisible({ timeout: 60_000 })
          await applicant.say(answer)
          await saysLive(applicant, pattern, why)
        })
      }
    } finally {
      await t.close()
    }
  })

  test(`S18 → S20 → S21 → S23 on one inquiry ${LIVE_ONLY}`, async ({ page, browser, request }) => {
    test.skip(!LIVE, 'live only: one real inquiry through every after-submit step')
    test.setTimeout(1_200_000)
    const t = await Tester.open(page, browser, request, 'S1')
    try {
      await t.blockA()
      const reference = await t.blockB()
      const seeded: Seeded = {
        reference,
        status: 'submitted',
        applicant_email: SARA.email,
        first_reviewer: REVIEWERS.reem.id,
        final_reviewer: REVIEWERS.faisal.id,
      }
      // S18
      const admin = await leasingAdminFromEmail(t, seeded)
      await approveDocument(admin, 'company_profile')
      await admin
        .getByTestId('doc-row-brand_profile')
        .getByLabel('Remarks (needed to reject)')
        .fill('Logo page missing')
      await admin.getByTestId('doc-reject-brand_profile').click()
      await admin
        .getByTestId('action-request_reupload')
        .getByRole('button', { name: 'Request re-upload' })
        .click()
      const reupload = await openCaseChatFromEmail(t, {
        to: SARA.email,
        template: 'reupload_request',
        reference,
        script: '',
      })
      await reupload.say('what do you need from me?')
      expect(await reupload.lastReply()).toMatch(/Brand Profile/)
      await reupload.upload('Brand Profile', 'brand_profile.pdf')
      await reupload.resubmitDocuments()
      // S20
      await admin.reload()
      await approveFirstLevel(admin)
      const status = await openCaseChatFromEmail(t, {
        to: SARA.email,
        template: 'first_level_approved',
        reference,
        script: '',
      })
      await status.say('where is my inquiry?')
      expect(await status.lastReply()).toMatch(/Tenant Qualified|Regional Sales Manager/i)
      // S21: the RSM opens the case from their own email.
      const rsm = await t.window()
      await rsm.goto(
        await inboxLink(rsm, {
          to: REVIEWERS.faisal.email,
          template: 'review_assigned',
          reference,
          contains: '/review/cases/',
        }),
      )
      await assignUnit(rsm)
      const requests = rsm.getByTestId('action-requests')
      await requests
        .getByLabel('Note for the applicant (optional)')
        .fill('Please share 12-month forecasted sales')
      await requests.getByRole('button', { name: 'Request Forecasted Sales Data' }).click()
      const sales = await openCaseChatFromEmail(t, {
        to: SARA.email,
        template: 'sales_data_request',
        reference,
        script: '',
      })
      await sales.say('here it is')
      await expect(sales.page.getByTestId('sales-data-upload-card')).toBeVisible({
        timeout: 120_000,
      })
      await sales.uploadForecastedSalesData('company_profile.pdf')
      await sales.submitForecastedSalesData()
      await rsm.reload()
      await rsm.getByTestId('approve-lead-yes').click()
      await expect(rsm.getByTestId('case-stage')).toHaveText('Lead Approved')
      // S23
      const contacts = await openCaseChatFromEmail(t, {
        to: SARA.email,
        template: 'contacts_request',
        reference,
        script: '',
      })
      await expect(contacts.cards('signatory_question')).toBeVisible({ timeout: 120_000 })
      await contacts.answerSignatoryQuestion(false)
      await contacts.say('Ahmed Saleh signs, ahmed@beanstreet.example, 0507654321')
      await contacts.say('billing is Nora Ali, nora@beanstreet.example, 0509998877')
      await expect(
        contacts.cards('contacts').last().getByTestId('contact-row-billing_contact'),
      ).toContainText('Nora', {
        timeout: 120_000,
      })
      await contacts.submitContacts()
      await rsm.reload()
      await rsm.getByTestId('approve-lead-final').click()
      await expect(rsm.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
      const inbox = await t.window()
      await inboxMessage(inbox, { to: SARA.email, template: 'inquiry_accepted', reference })
    } finally {
      await t.close()
    }
  })
})
