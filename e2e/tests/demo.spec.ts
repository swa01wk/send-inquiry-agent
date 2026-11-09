import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  expect,
  test,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Page,
} from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { fetchDevAudit, readDoneEventCount } from '../support/events'
import { fieldSource } from '../support/draft'
import { beat, caption, demoTestTimeoutMs } from '../support/demoPace'
import { fetchDevOutbox, smsOtpCode, type OutboxRow } from '../support/outbox'
import {
  assertDevPersonasOpenInOneClick,
  openCaseAs,
  resetDemoFromDevPage,
} from '../support/stories'
import { reviewerFor } from '../support/submit'
import { afterTurnChecks } from '../support/turnChecks'

/**
 * Day R5 (demo feedback §3.6, D10): the 10 Nov re-demo, beat by beat, with three browser
 * contexts: the applicant (`page`), the Lease Admin and the RLM.
 *
 * Two tests:
 * - "runs the 10 Nov walkthrough": the scripted agent on the Playwright stack (`make e2e-demo`).
 *   The restart beat is skipped there, since Playwright owns that backend.
 * - "survives a backend restart": only against the Docker demo stack on Postgres
 *   (`make demo`, then `make e2e-demo-stack`). It uses the seeded Case B, so it needs no model.
 *
 * Step 11 stops at Leasing Opportunities: the signed-in new-brand flow (R4) is shown as designed.
 */

const API = 'http://127.0.0.1:8000'
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const DEMO_STACK = process.env.E2E_DEMO_STACK === '1'

const APPLICANT_EMAIL = 'sara@beanstreet.example'
const APPLICANT_MOBILE = '+966501234567'
const BRAND_BUNDLE =
  'Specialty coffee kiosk at Riyadh Mall A. Sara Ali, sara@beanstreet.example, 0501234567'
const CASE_B_APPLICANT = 'khalid@desertbloom.example'

test.use({ video: 'on', trace: 'on' })

type DemoCase = {
  key: 'A' | 'B' | 'C'
  reference: string
  status: string
  first_reviewer: string | null
  final_reviewer: string | null
}

async function demoCases(request: APIRequestContext): Promise<DemoCase[]> {
  const res = await request.get(`${API}/api/dev/demo-cases`)
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as DemoCase[]
}

async function newContext(browser: Browser, page: Page): Promise<BrowserContext> {
  const viewport = page.viewportSize()
  const context = await browser.newContext(viewport ? { viewport } : {})
  // A click or file chooser never waits longer than this, so a stuck beat fails with a call
  // log instead of running out the whole test budget.
  context.setDefaultTimeout(120_000)
  return context
}

/** Newest email of `template` with a link that mentions `reference`. */
async function mailFor(
  request: APIRequestContext,
  template: string,
  reference: string,
  to?: string,
): Promise<OutboxRow> {
  const encoded = encodeURIComponent(reference)
  const find = (rows: OutboxRow[]) =>
    rows.find(
      (m) =>
        m.template === template &&
        m.links.some((l) => l.includes(reference) || l.includes(encoded)),
    )
  await expect
    .poll(async () => Boolean(find(await fetchDevOutbox(request, to))), {
      message: `${template} email for ${reference}`,
      timeout: 30_000,
    })
    .toBe(true)
  return find(await fetchDevOutbox(request, to))!
}

/** Newest email of `template` to `to` (for mails whose links carry a token, not the reference). */
async function latestMail(
  request: APIRequestContext,
  template: string,
  to: string,
  count = 1,
): Promise<OutboxRow> {
  const rows = async () =>
    (await fetchDevOutbox(request, to)).filter((m) => m.template === template)
  await expect
    .poll(async () => (await rows()).length, { message: `${count} × ${template} to ${to}` })
    .toBeGreaterThanOrEqual(count)
  return (await rows())[0]
}

function caseLink(mail: OutboxRow, scenario: string): string {
  const link = mail.links.find((l) => l.includes('/inquiry/case'))
  expect(link, `case link in ${mail.template}`).toBeTruthy()
  const url = new URL(link!)
  url.searchParams.set('e2eCaseScenario', scenario)
  return url.toString()
}

function relative(link: string): string {
  const url = new URL(link)
  return `${url.pathname}${url.search}`
}

async function answerCrNo(inquiry: InquiryPage): Promise<void> {
  const doneBefore = await readDoneEventCount(inquiry.page)
  await inquiry
    .cards('cr_question')
    .getByRole('button', { name: /no, we don't/i })
    .click()
  await inquiry.waitForTurnDone(doneBefore)
  await afterTurnChecks(inquiry)
}

async function verifyContact(inquiry: InquiryPage, request: APIRequestContext): Promise<void> {
  await expect(inquiry.cards('verification')).toBeVisible({ timeout: 60_000 })
  await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL)
  await inquiry.enterCode(smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)))
}

async function waitForHealth(request: APIRequestContext, timeoutMs = 180_000): Promise<void> {
  await expect
    .poll(
      async () => {
        try {
          return (await request.get(`${API}/api/health`, { timeout: 5_000 })).ok()
        } catch {
          return false
        }
      },
      { message: 'backend healthy after restart', timeout: timeoutMs, intervals: [1_000, 2_000] },
    )
    .toBe(true)
}

/** `test.step` that also prints the elapsed time, so a slow or stuck beat shows in the log. */
async function beatStep(title: string, body: () => Promise<void>): Promise<void> {
  const started = Date.now()
  console.log(`[demo] ${title}`)
  await test.step(title, body)
  console.log(`[demo]   done in ${Math.round((Date.now() - started) / 1000)} s`)
}

test.describe('Demo script — 10 Nov @demo', () => {
  test('runs the 10 Nov walkthrough', async ({ page, browser, request }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-chrome', 'Demo is desktop-only')
    test.skip(DEMO_STACK, 'The Docker demo stack runs the live model; this test is scripted')
    test.setTimeout(demoTestTimeoutMs())

    page.context().setDefaultTimeout(120_000)
    await request.post(`${API}/api/dev/reset`)
    const seeded = await demoCases(request)

    let reference = ''
    const leaseAdminContext = await newContext(browser, page)
    const rlmContext = await newContext(browser, page)
    // The applicant's case chat opens from the emails in a context of its own, as in the
    // per-story specs (a fresh chat would otherwise resume the submitted session).
    const caseContext = await newContext(browser, page)
    const leaseAdminPage = await leaseAdminContext.newPage()
    const rlmPage = await rlmContext.newPage()
    const casePage = await caseContext.newPage()
    try {
      await beatStep('0. /dev opens every persona in one click', async () => {
        await caption(page, '0. /dev: personas and demo cases')
        await assertDevPersonasOpenInOneClick(page)
        if (seeded.length) {
          await page.goto('/dev')
          await expect(page.getByTestId('dev-demo-cases').getByRole('listitem')).toHaveCount(3)
        }
      })

      const inquiry = new InquiryPage(page)
      await beatStep(
        '1. New chat, turn by turn: CR? No → upload the profiles → submit (F1, F5, F6)',
        async () => {
          await caption(page, '1. Turn by turn: CR? No → "I\'ll upload the profiles" → submit')
          await inquiry.open('rd-type-or-upload')
          await expect(inquiry.cards('cr_question')).toBeVisible({ timeout: 60_000 })
          await beat(page)
          await answerCrNo(inquiry)
          await beat(page)
          await inquiry.say("I'll upload the profiles")
          await afterTurnChecks(inquiry)
          await beat(page)
          await inquiry.say(BRAND_BUNDLE)
          await afterTurnChecks(inquiry)
          await beat(page)
          await inquiry.confirmCard()
          await verifyContact(inquiry, request)
          await beat(page)

          await expect(inquiry.cards('document_upload')).toBeVisible({ timeout: 90_000 })
          await inquiry.upload('Company Profile', 'company_profile_match.pdf')
          const confirmCompany = page.getByTestId(/confirm-fields-/).last()
          await expect(confirmCompany).toContainText('Bean Street Trading Co.')
          await expect(confirmCompany).toContainText(
            /from: Company Profile, company_profile_match\.pdf/i,
          )
          await beat(page)
          await inquiry.confirmCard()
          await inquiry.upload('Brand Profile', 'brand_profile_match.pdf')
          await beat(page)
          await inquiry.confirmCard()

          const draft = await inquiry.draft()
          expect(fieldSource(draft, 'company_name')).toBe('derived')
          expect(fieldSource(draft, 'brand_name_en')).toBe('derived')
          await expect(inquiry.cards('review')).toBeVisible({ timeout: 90_000 })
          await beat(page)
          await inquiry.acceptAndSubmit()
          reference = await inquiry.successReference()
          expect(reference).toMatch(/GEO-/)
          await beat(page)
        },
      )

      const leaseAdmin = await reviewerFor(request, reference, 'first')
      const rlm = await reviewerFor(request, reference, 'final')

      await beatStep(
        '2. Lease Admin: open the case from "Inquiry for approval"; reject a profile, ask for it again (F7, F8)',
        async () => {
          const assigned = await mailFor(request, 'review_assigned', reference)
          const consoleLink = assigned.links.find((l) => l.includes('/review/cases/'))!
          await leaseAdminPage.goto(relative(consoleLink))
          await caption(leaseAdminPage, '2. Lease Admin: "Inquiry for approval" email → the case')
          await expect(leaseAdminPage.getByTestId('case-stage')).toHaveText('First review')
          await expect(
            leaseAdminPage.getByTestId('doc-expiry-status-company_profile'),
          ).toContainText('Valid until')
          const approveFirst = leaseAdminPage
            .getByTestId('action-approve_first')
            .getByRole('button', { name: 'Approve first level' })
          await expect(approveFirst).toBeDisabled()
          await beat(leaseAdminPage)

          await leaseAdminPage.getByTestId('doc-approve-company_profile').click()
          await expect(leaseAdminPage.getByTestId('doc-approval-company_profile')).toHaveText(
            'Approved',
          )
          await leaseAdminPage
            .getByTestId('doc-row-brand_profile')
            .getByLabel('Remarks (needed to reject)')
            .fill('The logo page is missing')
          await leaseAdminPage.getByTestId('doc-reject-brand_profile').click()
          await expect(leaseAdminPage.getByTestId('doc-approval-brand_profile')).toContainText(
            'Rejected: The logo page is missing',
          )
          await beat(leaseAdminPage)
          await leaseAdminPage
            .getByTestId('action-request_reupload')
            .getByRole('button', { name: 'Request re-upload' })
            .click()
          await expect(leaseAdminPage.getByTestId('case-stage')).toContainText(
            'waiting for re-upload',
          )
          await beat(leaseAdminPage)
        },
      )

      const caseChat = new InquiryPage(casePage)
      await beatStep('3. Applicant: case link → re-upload → resubmit', async () => {
        const mail = await latestMail(request, 'reupload_request', APPLICANT_EMAIL)
        await casePage.goto(caseLink(mail, 't2-reupload'))
        await caption(casePage, '3. Applicant: re-upload from the case link')
        const uploadCard = caseChat.cards('document_upload')
        await expect(uploadCard).toBeVisible({ timeout: 60_000 })
        await expect(uploadCard).toHaveAttribute('data-mode', 'reupload')
        await expect(uploadCard.getByText('The logo page is missing')).toBeVisible()
        await beat(casePage)
        await caseChat.upload('Brand Profile', 'brand_profile.pdf')
        await caseChat.resubmitDocuments()
        await expect(caseChat.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
          'First review',
        )
        await beat(casePage)
      })

      await beatStep(
        '4. Lease Admin: approve each document, then the first level (F8, F16)',
        async () => {
          await caption(leaseAdminPage, '4. Lease Admin: the new file needs approval again')
          await leaseAdminPage.reload()
          await expect(leaseAdminPage.getByTestId('doc-approval-brand_profile')).toHaveText(
            'Waiting for a decision',
          )
          await expect(leaseAdminPage.getByTestId('doc-approval-company_profile')).toHaveText(
            'Approved',
          )
          await beat(leaseAdminPage)
          await leaseAdminPage.getByTestId('doc-approve-brand_profile').click()
          await expect(leaseAdminPage.getByTestId('first-approval-blockers')).toHaveCount(0)
          await leaseAdminPage
            .getByTestId('action-approve_first')
            .getByRole('button', { name: 'Approve first level' })
            .click()
          await expect(leaseAdminPage.getByTestId('case-stage')).toHaveText('Lead — second review')
          await expect(leaseAdminPage.getByTestId('timeline')).toContainText(
            'Document rejected: brand profile',
          )
          await beat(leaseAdminPage)
        },
      )

      await beatStep(
        '5. Applicant: "Yes, I\'m the authorised signatory" → billing contact (F19)',
        async () => {
          const mail = await latestMail(request, 'contacts_request', APPLICANT_EMAIL)
          await casePage.goto(caseLink(mail, 'rd-contact-approval'))
          await caption(casePage, '5. Applicant: signatory question, then the billing contact')
          await caseChat.waitForChatReady()
          await expect(caseChat.cards('signatory_question')).toBeVisible({ timeout: 60_000 })
          await beat(casePage)
          await caseChat.answerSignatoryQuestion(true)
          await expect(caseChat.cards('signatory_question')).toContainText(
            "Yes, I'm the authorised signatory",
          )
          const audit = await fetchDevAudit(request, caseChat.sessionId!)
          expect(audit.some((e) => e.type === 'signatory_answered')).toBe(true)
          await caseChat.say('Ready for billing details.')
          await expect(caseChat.cards('contacts')).toBeVisible({ timeout: 60_000 })
          await beat(casePage)
          await caseChat.submitContacts()
          await beat(casePage)
        },
      )

      await beatStep(
        '6. Lease Admin rejects the billing contact; the applicant fixes it; approve (F16)',
        async () => {
          await caption(leaseAdminPage, '6. Lease Admin: approve each contact')
          await leaseAdminPage.reload()
          await expect(
            leaseAdminPage.getByTestId('contact-approval-authorized_signatory'),
          ).toHaveText('Approved')
          await expect(leaseAdminPage.getByTestId('contact-approval-billing_contact')).toHaveText(
            'Waiting for approval',
          )
          await leaseAdminPage
            .getByTestId('contact-row-billing_contact')
            .getByLabel('Remarks (needed to reject)')
            .fill('Use the finance mailbox')
          await leaseAdminPage.getByTestId('contact-reject-billing_contact').click()
          await expect(
            leaseAdminPage.getByTestId('contact-approval-billing_contact'),
          ).toContainText('Rejected: Use the finance mailbox')
          await beat(leaseAdminPage)

          const fix = await latestMail(request, 'contacts_request', APPLICANT_EMAIL, 2)
          await casePage.goto(caseLink(fix, 'rd-contact-approval'))
          await caption(casePage, '6. Applicant: fix the billing contact')
          await caseChat.waitForChatReady()
          const contacts = caseChat.cards('contacts')
          await expect(contacts).toBeVisible({ timeout: 60_000 })
          await expect(contacts).toContainText('Use the finance mailbox')
          const billingRow = contacts.getByTestId('contact-row-billing_contact')
          if (!(await billingRow.getByText('finance@beanstreet.example').count())) {
            await caseChat.say('Here is the updated billing email.')
          }
          await expect(billingRow).toContainText('finance@beanstreet.example', { timeout: 60_000 })
          await beat(casePage)
          await caseChat.submitContacts()

          await leaseAdminPage.reload()
          await expect(leaseAdminPage.getByTestId('contact-approval-billing_contact')).toHaveText(
            'Waiting for approval',
          )
          await leaseAdminPage.getByTestId('contact-approve-billing_contact').click()
          await expect(leaseAdminPage.getByTestId('contact-approval-billing_contact')).toHaveText(
            'Approved',
          )
          await beat(leaseAdminPage)
        },
      )

      await beatStep('7. Restart the backend (Docker demo stack only)', async () => {
        testInfo.annotations.push({
          type: 'skipped step',
          description:
            'Playwright owns this backend. The restart runs in "survives a backend restart" against `make demo` (E2E_DEMO_STACK=1).',
        })
        for (const p of [page, casePage, leaseAdminPage]) await p.reload()
        await expect(leaseAdminPage.getByTestId('contact-approval-billing_contact')).toHaveText(
          'Approved',
        )
      })

      await beatStep('8. RLM: approve → Yardi', async () => {
        await openCaseAs(rlmPage, rlm, reference)
        await caption(rlmPage, '8. RLM: final approval → Yardi')
        await expect(rlmPage.getByTestId('approval-blockers')).toHaveCount(0)
        await beat(rlmPage)
        await rlmPage.getByTestId('action-approve').getByRole('button', { name: 'Approve' }).click()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
        await beat(rlmPage)
        await latestMail(request, 'inquiry_accepted', APPLICANT_EMAIL)
      })

      await beatStep('9. Applicant: the tracking page shows the outcome', async () => {
        await caption(page, '9. Applicant: tracking page')
        const submitted = (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
          (m) => m.template === 'submission_email',
        )
        const track = submitted
          .flatMap((m) => m.links)
          .find((l) => l.includes('/inquiry/status/') && l.includes(encodeURIComponent(reference)))
        expect(track, 'tracking link for this case').toBeTruthy()
        await page.goto(relative(track!))
        await expect(page.getByTestId('inquiry-status-page')).toBeVisible()
        await expect(
          page.getByText(/Approved — your details are with the leasing team for a proposal/i),
        ).toBeVisible()
        await beat(page)
      })

      await beatStep(
        '10. Second chat: typed company, mismatching profile → warning → flag in the brief (F6)',
        async () => {
          await caption(page, '10. Typed company, then a profile that says otherwise')
          const typedContext = await newContext(browser, page)
          const typedPage = await typedContext.newPage()
          const typed = new InquiryPage(typedPage)
          try {
            await typed.open('rd-type-or-upload-typed')
            await expect(typed.cards('cr_question')).toBeVisible({ timeout: 60_000 })
            await answerCrNo(typed)
            await typed.say("I'll type them")
            await typed.say('My Coffee Shop LLC, Olaya Street, Riyadh')
            await afterTurnChecks(typed)
            await typed.say(BRAND_BUNDLE)
            await afterTurnChecks(typed)
            await typed.confirmCard()
            await verifyContact(typed, request)
            await expect(typed.cards('document_upload')).toBeVisible({ timeout: 90_000 })
            await typed.upload('Company Profile', 'company_profile_mismatch.pdf')
            expect((await typed.lastReply()).toLowerCase()).toMatch(
              /company name|different|profile/,
            )
            await beat(typedPage)
            await typed.say('Keep my company name')
            await typed.upload('Brand Profile', 'brand_profile_match.pdf')
            await typed.confirmCard()
            await expect(typed.cards('review')).toBeVisible({ timeout: 90_000 })
            await typed.acceptAndSubmit()
            const typedReference = await typed.successReference()

            await caption(leaseAdminPage, '10. Lease Admin: the profile check in the case brief')
            await openCaseAs(leaseAdminPage, leaseAdmin, typedReference)
            await expect(leaseAdminPage.getByTestId('document-check-company_name')).toBeVisible({
              timeout: 30_000,
            })
            await beat(leaseAdminPage)
          } catch (error) {
            console.log('[demo] step 10 replies', JSON.stringify(await typed.allReplies(), null, 1))
            throw error
          } finally {
            await typedContext.close()
          }
        },
      )

      await beatStep(
        '11. "Yes, I have a CR" → sign in → Leasing Opportunities (F2; F3 shown as designed)',
        async () => {
          await caption(page, '11. CR? Yes → sign in → Leasing Opportunities')
          const crContext = await newContext(browser, page)
          const crPage = await crContext.newPage()
          const cr = new InquiryPage(crPage)
          try {
            await cr.open('rd-cr-question')
            await expect(cr.cards('cr_question')).toBeVisible({ timeout: 60_000 })
            const doneBefore = await readDoneEventCount(crPage)
            await cr
              .cards('cr_question')
              .getByRole('button', { name: /yes, we have a cr/i })
              .click()
            await cr.waitForTurnDone(doneBefore)
            const signIn = cr.cards('sign_in_prompt')
            await expect(signIn).toBeVisible({ timeout: 60_000 })
            await beat(crPage)
            const link = signIn.getByRole('link', { name: /sign in to tenant central/i })
            await expect(link).toHaveAttribute('href', /\/tenant\/?$/)
            await link.click()
            await expect(crPage.getByTestId('tenant-sign-in')).toBeVisible({ timeout: 30_000 })
            await crPage.getByLabel('Company').selectOption({ index: 1 })
            await crPage.getByRole('button', { name: 'Sign in' }).click()
            await expect(
              crPage.getByRole('heading', { name: /leasing opportunities/i }),
            ).toBeVisible()
            await beat(crPage)
          } finally {
            await crContext.close()
          }
        },
      )

      await beatStep(
        '12. Seeded Case A: expired and expiring-soon profiles, the mismatch flag (F8, F6)',
        async () => {
          const caseA = seeded.find((c) => c.key === 'A')
          if (!caseA) {
            testInfo.annotations.push({
              type: 'skipped step',
              description:
                'No seeded cases: the backend ran without DEMO_SEED (npm run test:demo sets it).',
            })
            return
          }
          await caption(leaseAdminPage, '12. Case A (seeded): expiry chips and a profile check')
          await openCaseAs(
            leaseAdminPage,
            { id: caseA!.first_reviewer!, name: '' },
            caseA!.reference,
          )
          await expect(
            leaseAdminPage.getByTestId('doc-expiry-status-company_profile'),
          ).toContainText('Expired on')
          await expect(leaseAdminPage.getByTestId('doc-approve-company_profile')).toBeDisabled()
          await expect(leaseAdminPage.getByTestId('doc-expiry-status-brand_profile')).toContainText(
            'Expiring soon',
          )
          await expect(leaseAdminPage.getByTestId('document-check-company_name')).toBeVisible()
          await beat(leaseAdminPage)
        },
      )

      await beatStep('Reset demo: fresh seeds, nothing left for the live applicant', async () => {
        await caption(page, 'Reset demo')
        await resetDemoFromDevPage(page)
        expect(await fetchDevOutbox(request, APPLICANT_EMAIL)).toHaveLength(0)
        if (seeded.length) {
          const after = await demoCases(request)
          expect(after.map((c) => c.key)).toEqual(['A', 'B', 'C'])
          expect(after.map((c) => c.reference)).not.toEqual(seeded.map((c) => c.reference))
        }
      })
    } finally {
      await leaseAdminContext.close()
      await rlmContext.close()
      await caseContext.close()
    }
  })

  test('survives a backend restart (Docker demo stack, Postgres)', async ({
    page,
    browser,
    request,
  }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-chrome', 'Demo is desktop-only')
    test.skip(!DEMO_STACK, 'Needs `make demo` running; run with `make e2e-demo-stack`')
    test.setTimeout(demoTestTimeoutMs())

    await request.post(`${API}/api/dev/reset`)
    const seeded = await demoCases(request)
    const caseB = seeded.find((c) => c.key === 'B')
    expect(caseB?.status).toBe('second_review')

    const rlmContext = await newContext(browser, page)
    try {
      await beatStep('Lease Admin approves the billing contact on Case B', async () => {
        await caption(page, 'Case B: Lease Admin approves the billing contact')
        await page.goto('/dev')
        await page
          .getByTestId('dev-demo-case-B')
          .getByRole('link', { name: 'as Lease Admin' })
          .click()
        await expect(page.getByTestId('case-stage')).toHaveText('Lead — second review')
        await page.getByTestId('contact-approve-billing_contact').click()
        await expect(page.getByTestId('contact-approval-billing_contact')).toHaveText('Approved')
        await beat(page)
      })

      await beatStep('7. Restart the backend and reload: nothing is lost', async () => {
        await caption(page, '7. docker compose restart backend')
        execFileSync(
          'docker',
          [
            'compose',
            '-f',
            'docker-compose.yml',
            '-f',
            'docker-compose.demo.yml',
            'restart',
            'backend',
          ],
          { cwd: REPO_ROOT, stdio: 'inherit' },
        )
        await waitForHealth(request)
        expect(await demoCases(request)).toEqual(seeded)
        await page.reload()
        await expect(page.getByTestId('case-stage')).toHaveText('Lead — second review')
        await expect(page.getByTestId('contact-approval-billing_contact')).toHaveText('Approved')
        await beat(page)
      })

      await beatStep('8. RLM: approve → Yardi; the applicant is told', async () => {
        const rlmPage = await rlmContext.newPage()
        await openCaseAs(rlmPage, { id: caseB!.final_reviewer!, name: '' }, caseB!.reference)
        await caption(rlmPage, '8. RLM: final approval → Yardi')
        await expect(rlmPage.getByTestId('approval-blockers')).toHaveCount(0)
        await rlmPage.getByTestId('action-approve').getByRole('button', { name: 'Approve' }).click()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
        await latestMail(request, 'inquiry_accepted', CASE_B_APPLICANT)
        await beat(rlmPage)
      })
    } finally {
      await rlmContext.close()
    }
  })
})
