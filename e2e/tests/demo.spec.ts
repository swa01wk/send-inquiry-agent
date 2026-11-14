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
import { fetchDevAudit } from '../support/events'
import { fieldDisplay } from '../support/draft'
import { beat, caption, demoTestTimeoutMs } from '../support/demoPace'
import { fetchDevOutbox, type OutboxRow } from '../support/outbox'
import {
  assertDevPersonasOpenInOneClick,
  openCaseAs,
  resetDemoFromDevPage,
  raiseNewBrandFromOpportunities,
} from '../support/stories'
import { expectFlowPath } from '../support/flowV2'
import { demoPath, scenario } from '../support/scenarios'
import { openEntryChat, runStep } from '../support/steps'
import { reviewerFor } from '../support/submit'

/**
 * Flow v2 day F5: docs/demo-script.md, beat by beat, with browser contexts for the applicant
 * (`page`), the Leasing Admin, the Regional Sales Manager and the applicant's case chat.
 * Beat 1 is the catalogue's `demo` path (docs/flow-v2/scenarios.json, script `flow-v2-demo`);
 * beats 12 and 13 run the catalogue's S3 and CC1 with their own scripts.
 *
 * Two tests:
 * - "runs the walkthrough": the scripted agent on the Playwright stack (`make e2e-demo`).
 *   The restart beat is skipped there, since Playwright owns that backend.
 * - "survives a backend restart": only against the Docker demo stack on Postgres
 *   (`make demo`, then `make e2e-demo-stack`). It uses the seeded Case B, so it needs no model.
 */

const API = 'http://127.0.0.1:8000'
const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const DEMO_STACK = process.env.E2E_DEMO_STACK === '1'

const APPLICANT_EMAIL = 'sara@beanstreet.example'
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

test.describe('Demo script — flow v2 @demo', () => {
  test('runs the walkthrough', async ({ page, browser, request }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop-chrome', 'Demo is desktop-only')
    test.skip(DEMO_STACK, 'The Docker demo stack runs the live model; this test is scripted')
    test.setTimeout(demoTestTimeoutMs())

    page.context().setDefaultTimeout(120_000)
    await request.post(`${API}/api/dev/reset`)
    const seeded = await demoCases(request)
    if (process.env.E2E_DEMO_SEED === '1' && process.env.CI) {
      // `make e2e-demo` starts its own backend with DEMO_SEED, so the seeds must be there.
      expect(seeded.map((c) => c.key)).toEqual(['A', 'B', 'C'])
    }

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

      await beatStep(
        "1. Public page in the app's order: CR? Skip → Office → two malls → submit (flow v2)",
        async () => {
          await caption(page, '1. Public page: Skip the CR → Office → two malls → submit')
          const entry = demoPath()
          const ctx = await openEntryChat(page, browser, request, entry, false)
          for (const step of entry.steps ?? []) {
            await test.step(JSON.stringify(step).slice(0, 80), () => runStep(ctx, step))
            await beat(page)
          }
          const inquiry = ctx.chat
          reference = await inquiry.successReference()
          expect(reference).toMatch(/GEO-/)
          await expectFlowPath(request, inquiry.sessionId!, entry.chart_paths)
          // AGENT-DET checks the stored values; here, what the draft panel shows.
          const draft = await inquiry.draft()
          expect(fieldDisplay(draft, 'unit_type')).toMatch(/office/i)
          expect(fieldDisplay(draft, 'malls')).toMatch(/Riyadh Mall A/)
          expect(fieldDisplay(draft, 'malls')).toMatch(/Jeddah Mall A/)
          await beat(page)
        },
      )

      const leaseAdmin = await reviewerFor(request, reference, 'first')
      const rlm = await reviewerFor(request, reference, 'final')

      await beatStep(
        '2. Leasing Admin: open the case from "Inquiry for approval"; reject a profile, ask for it again (F7, F8, S18)',
        async () => {
          const assigned = await mailFor(request, 'review_assigned', reference)
          const consoleLink = assigned.links.find((l) => l.includes('/review/cases/'))!
          await leaseAdminPage.goto(relative(consoleLink))
          await caption(leaseAdminPage, '2. Leasing Admin: "Inquiry for approval" email → the case')
          await expect(leaseAdminPage.getByTestId('case-stage')).toHaveText(
            'With the Leasing Admin',
          )
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
            .fill('Logo page missing')
          await leaseAdminPage.getByTestId('doc-reject-brand_profile').click()
          await expect(leaseAdminPage.getByTestId('doc-approval-brand_profile')).toContainText(
            'Rejected: Logo page missing',
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
      await beatStep(
        '3. Applicant: case link → "what do you need from me?" → re-upload → resubmit (S18)',
        async () => {
          const mail = await latestMail(request, 'reupload_request', APPLICANT_EMAIL)
          await casePage.goto(caseLink(mail, 'flow-v2-s18'))
          await caption(casePage, '3. Applicant: re-upload from the case link')
          await caseChat.waitForChatReady()
          const uploadCard = caseChat.cards('document_upload')
          await expect(uploadCard).toBeVisible({ timeout: 60_000 })
          await expect(uploadCard).toHaveAttribute('data-mode', 'reupload')
          await expect(uploadCard.getByText('Logo page missing')).toBeVisible()
          await caseChat.say('what do you need from me?')
          expect(await caseChat.lastReply()).toMatch(/Brand Profile/)
          await beat(casePage)
          await caseChat.upload('Brand Profile', 'brand_profile.pdf')
          await caseChat.resubmitDocuments()
          await expect(caseChat.cards('case_status').getByRole('heading', { level: 3 })).toHaveText(
            'With the Leasing Admin',
          )
          await beat(casePage)
        },
      )

      await beatStep(
        '4. Leasing Admin: approve the new file, then Approve Prospective Tenant? = Yes (F8, F16)',
        async () => {
          await caption(leaseAdminPage, '4. Leasing Admin: the new file needs approval again')
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
          await expect(leaseAdminPage.getByTestId('case-stage')).toHaveText('Tenant Qualified')
          await expect(leaseAdminPage.getByTestId('timeline')).toContainText(
            'Document rejected: brand profile',
          )
          await beat(leaseAdminPage)
        },
      )

      await beatStep(
        '5. Regional Sales Manager: assign the unit, ask for Forecasted Sales Data (S21)',
        async () => {
          await openCaseAs(rlmPage, rlm, reference)
          await caption(rlmPage, '5. Regional Sales Manager: unit, then Forecasted Sales Data')
          await expect(rlmPage.getByTestId('case-stage')).toHaveText('Tenant Qualified')
          await expect(rlmPage.getByTestId('lead-approval-blockers')).toContainText(
            'Assign the unit first',
          )
          await rlmPage.getByTestId('assign-unit-ref').fill('G-014')
          await rlmPage.getByTestId('assign-unit-area').fill('95')
          await rlmPage.getByTestId('assign-unit-submit').click()
          await expect(rlmPage.getByTestId('assigned-unit')).toContainText('G-014')
          await beat(rlmPage)
          const requests = rlmPage.getByTestId('action-requests')
          await requests
            .getByLabel('Note for the applicant (optional)')
            .fill('Monthly, first year.')
          await requests.getByRole('button', { name: 'Request Forecasted Sales Data' }).click()
          await expect(rlmPage.getByTestId('lead-approval-blockers')).toContainText(
            'Forecasted Sales Data not received yet',
          )
          await beat(rlmPage)
        },
      )

      await beatStep(
        '6. Applicant: sends the Forecasted Sales Data from the case chat',
        async () => {
          const mail = await latestMail(request, 'sales_data_request', APPLICANT_EMAIL)
          await casePage.goto(caseLink(mail, 'flow-v2-s21'))
          await caption(casePage, '6. Applicant: Forecasted Sales Data')
          await caseChat.waitForChatReady()
          await caseChat.say('here it is')
          await expect(casePage.getByTestId('sales-data-upload-card')).toBeVisible({
            timeout: 60_000,
          })
          await beat(casePage)
          await caseChat.uploadForecastedSalesData('company_profile.pdf')
          await caseChat.submitForecastedSalesData()
          await beat(casePage)
        },
      )

      await beatStep('7. Regional Sales Manager: "Approve Lead?" = Yes (flow v2)', async () => {
        await caption(rlmPage, '7. Regional Sales Manager: Approve Lead? = Yes')
        await rlmPage.reload()
        await expect(rlmPage.getByTestId('lead-approval-blockers')).toHaveCount(0)
        await rlmPage.getByTestId('approve-lead-yes').click()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Lead Approved')
        await expect(rlmPage.getByTestId('approve-lead-final')).toBeDisabled()
        await beat(rlmPage)
      })

      await beatStep(
        '8. Applicant: "Yes, I\'m the authorised signatory" → billing contact (F19)',
        async () => {
          const mail = await latestMail(request, 'contacts_request', APPLICANT_EMAIL)
          await casePage.goto(caseLink(mail, 'rd-contact-approval'))
          await caption(casePage, '8. Applicant: signatory question, then the billing contact')
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

      await beatStep('9. Restart the backend (Docker demo stack only)', async () => {
        testInfo.annotations.push({
          type: 'skipped step',
          description:
            'Playwright owns this backend. The restart runs in "survives a backend restart" against `make demo` (E2E_DEMO_STACK=1).',
        })
        for (const p of [page, casePage, rlmPage]) await p.reload()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Lead Approved')
      })

      await beatStep('10. Regional Sales Manager: the final Approve Lead → Yardi', async () => {
        await openCaseAs(rlmPage, rlm, reference)
        await caption(rlmPage, '10. Regional Sales Manager: Approve Lead → Yardi')
        await expect(rlmPage.getByTestId('approval-blockers')).toHaveCount(0)
        await beat(rlmPage)
        await rlmPage.getByTestId('approve-lead-final').click()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
        await beat(rlmPage)
        await latestMail(request, 'inquiry_accepted', APPLICANT_EMAIL)
        await expectFlowPath(request, reference, [
          ['qualified', 'prod2', 'rsm', 'fsd_q', 'fsd_notify', 'fsd_provide', 'approve_lead'],
          ['approve_lead', 'req_contacts', 'contacts_notify', 'contacts_provide', 'approve_lead2'],
        ])
      })

      await beatStep('11. Applicant: the tracking page shows the outcome', async () => {
        await caption(page, '11. Applicant: tracking page')
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
        '12. Registered CR → "already registered" → sign in → Leasing Opportunities → new brand (S3, F2, F3)',
        async () => {
          await caption(page, '12. A registered CR → sign in → Leasing Opportunities')
          const crContext = await newContext(browser, page)
          const crPage = await crContext.newPage()
          try {
            const entry = scenario('S3')
            const ctx = await openEntryChat(crPage, browser, request, entry, false)
            for (const step of entry.steps ?? []) await runStep(ctx, step)
            const signIn = ctx.chat.cards('sign_in_prompt').last()
            await expect(signIn).toBeVisible({ timeout: 60_000 })
            await expect(ctx.chat.cards('verification')).toHaveCount(0)
            await beat(crPage)
            const link = signIn.getByRole('link', { name: /sign in to tenant central/i })
            await expect(link).toHaveAttribute('href', /\/tenant\/?$/)
            await link.click()
            await expect(crPage.getByTestId('tenant-sign-in')).toBeVisible({ timeout: 30_000 })
            await crPage.getByLabel('Company').selectOption('T-1001') // Oasis Coffee Company
            await crPage.getByRole('button', { name: 'Sign in' }).click()
            await expect(
              crPage.getByRole('heading', { name: /leasing opportunities/i }),
            ).toBeVisible()
            await beat(crPage)

            // R4 (F3): the company from Yardi, the new brand from its Brand Profile, both
            // profiles, and the Company Profile checked against the Cenomi record.
            await caption(crPage, '12. Leasing Opportunities → a new brand')
            const { reference: newBrand } = await raiseNewBrandFromOpportunities(crPage, beat)
            await openCaseAs(leaseAdminPage, leaseAdmin, newBrand)
            await caption(leaseAdminPage, '12. Leasing Admin: Company Profile vs the Cenomi record')
            await expect(leaseAdminPage.getByTestId('document-check-company_name')).toBeVisible({
              timeout: 30_000,
            })
            await beat(leaseAdminPage)
          } finally {
            await crContext.close()
          }
        },
      )

      await beatStep(
        '13. Call centre: existing CR and contact → Inform → Email sign-in link (CC1)',
        async () => {
          const ccContext = await newContext(browser, page)
          const ccPage = await ccContext.newPage()
          try {
            const entry = scenario('CC1')
            const ctx = await openEntryChat(ccPage, browser, request, entry, false)
            await caption(ccPage, '13. Call centre: the caller already has a login')
            for (const step of entry.steps ?? []) {
              await runStep(ctx, step)
              await beat(ccPage)
            }
            await latestMail(request, 'sign_in_link', 'layla.hassan@oasiscoffee.example')
            await expectFlowPath(request, ctx.chat.sessionId!, entry.chart_paths, entry.not_path)
          } finally {
            await ccContext.close()
          }
        },
      )

      await beatStep(
        '14. Seeded Case A: expired and expiring-soon profiles, the mismatch flag (F8, F6)',
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
          await caption(leaseAdminPage, '14. Case A (seeded): expiry chips and a profile check')
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
    // Flow v2 (§3.7): case B is "Lead Approved" with its contacts in.
    expect(caseB?.status).toBe('lead_approved')

    const rlmContext = await newContext(browser, page)
    try {
      await beatStep('Case B: Lead Approved, contacts in', async () => {
        await caption(page, 'Case B: Lead Approved, ready for the final Approve Lead')
        await openCaseAs(page, { id: caseB!.final_reviewer!, name: '' }, caseB!.reference)
        await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
        await expect(page.getByTestId('approve-lead-final')).toBeEnabled()
        await beat(page)
      })

      await beatStep('9. Restart the backend and reload: nothing is lost', async () => {
        await caption(page, '9. docker compose restart backend')
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
        await expect(page.getByTestId('case-stage')).toHaveText('Lead Approved')
        await expect(page.getByTestId('approve-lead-final')).toBeEnabled()
        await beat(page)
      })

      await beatStep('10. RSM: the final Approve Lead → Yardi; the applicant is told', async () => {
        const rlmPage = await rlmContext.newPage()
        await openCaseAs(rlmPage, { id: caseB!.final_reviewer!, name: '' }, caseB!.reference)
        await caption(rlmPage, '10. Regional Sales Manager: Approve Lead → Yardi')
        await expect(rlmPage.getByTestId('approval-blockers')).toHaveCount(0)
        await rlmPage.getByTestId('approve-lead-final').click()
        await expect(rlmPage.getByTestId('case-stage')).toHaveText('Approved and sent to Yardi')
        await latestMail(request, 'inquiry_accepted', CASE_B_APPLICANT)
        await beat(rlmPage)
      })
    } finally {
      await rlmContext.close()
    }
  })
})
