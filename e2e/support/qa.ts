import {
  expect,
  test,
  type APIRequestContext,
  type Browser,
  type Locator,
  type Page,
} from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { withE2eScenario } from './outbox'
import { scenario, scriptFor, type CatalogueEntry, type CatalogueStep } from './scenarios'
import { openEntryChat, runStep, type StepCtx } from './steps'
import { advanceClockFromDevPage, openCaseAs, resetDemoFromDevPage } from './stories'

/**
 * docs/scenario-queries.md, automated the way a tester works through it: /dev to reset and
 * move the clock, the chat's cards and buttons, /dev/inbox for every email link, and the
 * reviewer console for the Leasing Admin and the Regional Sales Manager.
 *
 * Two modes, one spec:
 * - scripted (`make e2e-qa`): the scripted model from backend/tests/e2e_scripts, so the chat
 *   steps follow the catalogue's turns exactly. Checks what the app shows: cards, states,
 *   emails, the console. The agent's wording isn't checked (the script wrote it).
 * - live (`make e2e-qa-live`): the real model. The same checks, plus the doc's "what should
 *   happen" for the agent's replies, as tolerant patterns (`saysLive`).
 */
export const LIVE = Boolean(process.env.E2E_LIVE)
export const API = 'http://127.0.0.1:8000'

/** Tags: `@qa-scripted` runs in `make e2e-qa`, `@qa-live` in `make e2e-qa-live`. */
export const BOTH = '@qa @qa-scripted @qa-live'
export const SCRIPTED_ONLY = '@qa @qa-scripted'
export const LIVE_ONLY = '@qa @qa-live'

export const REFERENCE = /GEO-(STR|MED|SPC|OFF)-\d{6}/

export const SARA = {
  email: 'sara@beanstreet.example',
  basic:
    'Sara Ali, Bean Street Trading Co., King Fahd Road Al Olaya Riyadh, brand Bean Street / بين ستريت, sara@beanstreet.example, 0501234567',
}
export const LAYLA = {
  email: 'layla.hassan@oasiscoffee.example',
  basic:
    'Layla Hassan, Oasis Coffee Co., Tahlia Street Jeddah, brand Oasis Coffee / واحة القهوة, layla.hassan@oasiscoffee.example, 0505550101',
}
export const PROPERTY = 'Riyadh Mall A, 30 to 50 sqm, up to 250k a year, 3 years'

/** The doc's reviewer personas (backend/app/data/mock_world/reviewers.json). */
export const REVIEWERS = {
  reem: {
    id: 'lease_admin-central',
    name: 'Reem Al Mutairi',
    email: 'reem.almutairi@cenomi.example',
  },
  lama: {
    id: 'lease_admin-western',
    name: 'Lama Al Zahrani',
    email: 'lama.alzahrani@cenomi.example',
  },
  faisal: {
    id: 'rlm_store-central',
    name: 'Faisal Al Qahtani',
    email: 'faisal.alqahtani@cenomi.example',
  },
}

/** Block A and Block B of the doc, as catalogue steps (the same turns the scripts expect). */
export const A = {
  skip: [{ cr_skip: true }, { cr_skip_confirm: true }] as CatalogueStep[],
  store: [{ say: 'a store' }] as CatalogueStep[],
  sells: [{ say: 'we sell specialty coffee and pastries' }] as CatalogueStep[],
  confirmUnit: [{ confirm_card: 'unit_and_category' }] as CatalogueStep[],
  basic: (text = SARA.basic): CatalogueStep[] => [{ say: text }],
  confirmBasic: [{ confirm_card: 'basic_info' }] as CatalogueStep[],
  verify: [{ verify_email: true }, { enter_code: '1234' }] as CatalogueStep[],
}
export const B = {
  property: (text = PROPERTY): CatalogueStep[] => [{ say: text }],
  confirmProperty: [{ confirm_card: 'property_details' }] as CatalogueStep[],
  terms: [{ accept_terms: true }] as CatalogueStep[],
  upload: [
    { upload: { company_profile: 'company_profile.pdf', brand_profile: 'brand_profile.pdf' } },
  ] as CatalogueStep[],
  submit: [{ submit: true }] as CatalogueStep[],
}

/** One scenario's chat, opened the way the doc says, with the catalogue's script in scripted mode. */
export class Tester {
  private constructor(
    readonly ctx: StepCtx,
    readonly entry: CatalogueEntry,
  ) {}

  /** Setup step 1 (Reset demo on /dev), then the chat (or /callcentre for CC1–CC3). */
  static async open(
    page: Page,
    browser: Browser,
    request: APIRequestContext,
    id: string,
  ): Promise<Tester> {
    await test.step('Setup: Reset demo on /dev', () => resetDemoFromDevPage(page))
    const entry = scenario(id)
    const ctx = await openEntryChat(page, browser, request, entry, LIVE)
    return new Tester(ctx, entry)
  }

  /** Reset only: the after-submit scenarios start from a seeded case, not a chat. */
  static async blank(
    page: Page,
    browser: Browser,
    request: APIRequestContext,
    id: string,
  ): Promise<Tester> {
    await test.step('Setup: Reset demo on /dev', () => resetDemoFromDevPage(page))
    const entry = scenario(id)
    const ctx: StepCtx = {
      page,
      browser,
      request,
      entry,
      chat: new InquiryPage(page),
      live: LIVE,
      contexts: [],
    }
    return new Tester(ctx, entry)
  }

  /** Reset, then a plain chat with no script (the off-script checks: live only). */
  static async plain(page: Page, browser: Browser, request: APIRequestContext): Promise<Tester> {
    await test.step('Setup: Reset demo on /dev', () => resetDemoFromDevPage(page))
    const entry: CatalogueEntry = { id: 'off-script', title: 'Off-script', chart_paths: [] }
    const chat = new InquiryPage(page)
    await chat.open()
    const ctx: StepCtx = { page, browser, request, entry, chat, live: LIVE, contexts: [] }
    return new Tester(ctx, entry)
  }

  /**
   * CC2, CC3: the caller opens the application link from their email, in their own window;
   * the next steps act on that chat. Scripted runs use the catalogue's applicant script.
   */
  async openApplicationLinkFromInbox(to: string): Promise<void> {
    const window = await this.window()
    let path = await inboxLink(window, {
      to,
      template: 'complete_application',
      contains: '/inquiry/verify',
    })
    if (!LIVE) path = withE2eScenario(path, `${scriptFor(this.entry.id)}-applicant`)
    const applicant = new InquiryPage(window)
    await applicant.openApplicationVerifyLink(path)
    this.ctx.chat = applicant
  }

  get chat(): InquiryPage {
    return this.ctx.chat
  }

  get page(): Page {
    return this.ctx.chat.page
  }

  /** A doc row: its actions, then what should happen. */
  async row(label: string, steps: CatalogueStep[], check?: () => Promise<void>): Promise<void> {
    await test.step(label, async () => {
      for (const step of steps) await runStep(this.ctx, step)
      if (check) await check()
    })
  }

  /** Block A, rows A2–A7 (the chat is already open: A1). */
  async blockA(
    options: {
      basic?: string
      cr?: 'skip' | string
      /** Extra checks after a row, by its doc id. */
      after?: Partial<Record<'A2' | 'A4' | 'A5' | 'A6' | 'A7', () => Promise<void>>>
      /** Stop after this row (S6, S8 carry on by hand). */
      until?: 'A6'
    } = {},
  ): Promise<void> {
    const cr = options.cr ?? 'skip'
    const after = options.after ?? {}
    if (cr === 'skip') {
      await this.row('A2 Skip', [A.skip[0]], async () => {
        await expect(this.crCard().getByTestId('skip-confirm')).toContainText(
          'Are you sure you want to proceed without CR ID?',
        )
      })
      await this.row('A2 Yes, continue without it', [A.skip[1]], async () => {
        await expect(this.crCard()).toContainText('Continuing without a CR number.')
        await expectUnitChoices(this.page)
        await after.A2?.()
      })
    } else {
      await this.row(`Type ${cr} → Verify`, [{ cr_verify: cr }], async () => {
        await expect(this.crCard()).toContainText('not registered yet')
        await saysLive(this.chat, /store|office/i, 'moves on to Store or Office')
        await after.A2?.()
      })
    }
    await this.row('A3 a store', A.store)
    await this.row('A4 we sell specialty coffee and pastries', A.sells, async () => {
      await expect(this.chat.cards('confirm_fields').last()).toBeVisible()
      await after.A4?.()
    })
    await this.row('A5 Looks right', A.confirmUnit, async () => {
      await after.A5?.()
    })
    await this.row('A6 basic info in one message', A.basic(options.basic), async () => {
      await expect(this.chat.cards('verification').last()).toBeVisible({ timeout: 60_000 })
      await after.A6?.()
    })
    if (options.until === 'A6') return
    await this.row(
      'A7 Looks right → verification link → 1234',
      [...A.confirmBasic, ...A.verify],
      async () => {
        await expectVerified(this.chat)
        await after.A7?.()
      },
    )
  }

  /** Block B, rows B1–B5; returns the reference. */
  async blockB(
    options: { property?: string; from?: 'B1' | 'B3' | 'B4' | 'B5'; until?: 'B3' | 'B4' } = {},
  ): Promise<string> {
    const from = options.from ?? 'B1'
    if (from === 'B1') {
      await this.row('B1 mall, area, budget, lease', B.property(options.property), async () => {
        await expect(draftPanel(this.page)).toContainText(/Mall/)
      })
      await this.row('B2 Looks right', B.confirmProperty, async () => {
        await expect(this.chat.cards('terms').last()).toBeVisible()
      })
    }
    if (from === 'B1' || from === 'B3') {
      await this.row('B3 Tick the terms', B.terms, async () => {
        const docs = this.chat.cards('document_upload').last()
        await expect(docs).toContainText('Company Profile')
        await expect(docs).toContainText('Brand Profile')
      })
    }
    if (options.until === 'B3') return ''
    if (from !== 'B5') {
      await this.row('B4 Upload both profiles', B.upload, async () => {
        await expect(this.chat.cards('review').last()).toBeVisible({ timeout: 60_000 })
      })
    }
    await expectNoReferenceYet(this.chat)
    if (options.until === 'B4') return ''
    let reference = ''
    await this.row('B5 Submit inquiry', B.submit, async () => {
      reference = await this.chat.successReference()
    })
    return reference
  }

  crCard(): Locator {
    return this.chat.cards('company_registration').last()
  }

  /** A second browser window (another persona), closed with the tester. */
  async window(): Promise<Page> {
    const viewport = this.page.viewportSize()
    const context = await this.ctx.browser.newContext(viewport ? { viewport } : {})
    this.ctx.contexts.push(context)
    return context.newPage()
  }

  async close(): Promise<void> {
    for (const context of this.ctx.contexts) await context.close()
  }
}

// ---- What should happen: the app (both modes) -------------------------------------------

/** The "Your inquiry" panel beside the chat (desktop): every value saved so far. */
export function draftPanel(page: Page): Locator {
  return page.getByTestId('draft-scroll-body')
}

export async function expectUnitChoices(page: Page): Promise<void> {
  await expect(page.getByRole('button', { name: 'Store', exact: true }).last()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Office', exact: true }).last()).toBeVisible()
  // A3: only Store and Office this round.
  await expect(page.getByRole('button', { name: /^(Media|Specialty)$/ })).toHaveCount(0)
}

export async function expectVerified(chat: InquiryPage): Promise<void> {
  await expect(chat.cards('verification').last()).toContainText(/Email and mobile verified/, {
    timeout: 60_000,
  })
}

/** "It never says submitted before the reference shows." */
export async function expectNoReferenceYet(chat: InquiryPage): Promise<void> {
  await expect(chat.cards('success')).toHaveCount(0)
  for (const reply of await chat.allReplies()) expect(reply).not.toMatch(REFERENCE)
}

/** No reply repeats a number the user typed (S2: the CR). */
export async function expectNeverRepeats(chat: InquiryPage, text: string): Promise<void> {
  for (const reply of await chat.allReplies()) expect(reply).not.toContain(text)
}

// ---- What should happen: the agent's words (live only) ----------------------------------

/** The doc's check on the agent's newest reply; scripted runs skip it (the script wrote it). */
export async function saysLive(chat: InquiryPage, pattern: RegExp, why: string): Promise<void> {
  if (!LIVE) return
  const reply = await chat.lastReply()
  expect(reply, why).toMatch(pattern)
}

export async function neverSaysLive(
  chat: InquiryPage,
  pattern: RegExp,
  why: string,
): Promise<void> {
  if (!LIVE) return
  for (const reply of await chat.allReplies()) expect(reply, why).not.toMatch(pattern)
}

/** Arabic script in the newest reply. */
export const ARABIC = /[؀-ۿ]/

// ---- /dev and /dev/inbox -------------------------------------------------------------------

export async function devClock(page: Page, button: '+24 h' | '+48 h'): Promise<void> {
  await test.step(`/dev ${button}`, () => advanceClockFromDevPage(page, button))
}

/** The clock helper from the doc's setup (curl … /api/dev/clock/advance). */
export async function advanceHours(request: APIRequestContext, hours: number): Promise<void> {
  const res = await request.post(`${API}/api/dev/clock/advance`, { data: { hours } })
  expect(res.ok(), await res.text()).toBeTruthy()
}

/** The seed helper from the doc's setup (curl … /api/dev/flow/seed). */
export interface Seeded {
  reference: string
  status: string
  applicant_email: string
  first_reviewer: string | null
  final_reviewer: string | null
}

export async function seedCase(
  request: APIRequestContext,
  body: {
    stage: 'submitted' | 'qualified' | 'lead_approved'
    cr_number?: string
    malls?: string[]
    unit_type?: string
  },
): Promise<Seeded> {
  const res = await request.post(`${API}/api/dev/flow/seed`, { data: body })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as Seeded
}

/** One message in /dev/inbox, found the way a tester does: filter by recipient, then read. */
export function inboxItems(page: Page): Locator {
  return page.getByTestId('dev-inbox-page').locator('li:has(> pre)')
}

export async function openInbox(page: Page, to: string): Promise<void> {
  await page.goto('/dev/inbox')
  await expect(page.getByTestId('dev-inbox-page')).toBeVisible()
  await page.getByPlaceholder('Filter by email or phone').fill(to)
}

export async function inboxMessage(
  page: Page,
  opts: { to: string; template: string; reference?: string },
): Promise<Locator> {
  let item: Locator = inboxItems(page).filter({ hasText: opts.template })
  if (opts.reference) item = item.filter({ hasText: opts.reference })
  // The inbox loads once; a message sent a moment ago needs a reload.
  await expect(async () => {
    await openInbox(page, opts.to)
    await expect(item.first()).toBeVisible({ timeout: 3_000 })
  }).toPass({ timeout: 30_000 })
  return item.first()
}

export async function expectNoInboxMessage(
  page: Page,
  opts: { to: string; template: string; reference?: string },
): Promise<void> {
  await openInbox(page, opts.to)
  await expect(page.getByText('Loading…')).toHaveCount(0)
  let item: Locator = inboxItems(page).filter({ hasText: opts.template })
  if (opts.reference) item = item.filter({ hasText: opts.reference })
  await expect(item).toHaveCount(0)
}

/** The link in an inbox message, as a path on the app (the tester clicks it). */
export async function inboxLink(
  page: Page,
  opts: { to: string; template: string; reference?: string; contains: string },
): Promise<string> {
  const message = await inboxMessage(page, opts)
  const href = await message
    .getByRole('link')
    .filter({ hasText: opts.contains })
    .first()
    .getAttribute('href')
  expect(href, `${opts.template} link to ${opts.contains}`).toBeTruthy()
  const url = new URL(href!)
  return `${url.pathname}${url.search}`
}

/**
 * The case chat from an email: the applicant's own window. Scripted runs add the case
 * chat's script (`e2eCaseScenario`), as the flow-v2 specs do.
 */
export async function openCaseChatFromEmail(
  t: Tester,
  opts: { to: string; template: string; reference: string; script: string },
): Promise<InquiryPage> {
  const inbox = await t.window()
  let path = await inboxLink(inbox, { ...opts, contains: '/inquiry/case' })
  if (!LIVE) {
    const url = new URL(path, 'http://x')
    url.searchParams.set('e2eCaseScenario', opts.script)
    path = `${url.pathname}${url.search}`
  }
  await inbox.goto(path)
  const chat = new InquiryPage(inbox)
  await chat.waitForChatReady()
  return chat
}

// ---- The reviewer console ----------------------------------------------------------------

/** A reviewer's window on a case: the email link signs them in, as in the doc. */
export async function openCaseAsReviewer(
  t: Tester,
  reviewer: { id: string; name: string },
  reference: string,
): Promise<Page> {
  const page = await t.window()
  await openCaseAs(page, reviewer, reference)
  return page
}

export async function approveDocument(
  page: Page,
  docType: 'company_profile' | 'brand_profile',
): Promise<void> {
  const button = page.getByTestId(`doc-approve-${docType}`)
  if ((await button.count()) > 0) await button.click()
  await expect(page.getByTestId(`doc-approval-${docType}`)).toHaveText('Approved')
}

export async function approveFirstLevel(page: Page): Promise<void> {
  await approveDocument(page, 'company_profile')
  await approveDocument(page, 'brand_profile')
  await expect(page.getByTestId('first-approval-blockers')).toHaveCount(0)
  await page
    .getByTestId('action-approve_first')
    .getByRole('button', { name: 'Approve first level' })
    .click()
  await expect(page.getByTestId('case-stage')).toHaveText('Tenant Qualified')
}

export async function rejectWith(
  page: Page,
  reason: 'not_a_fit' | 'no_space',
  remarks: string,
): Promise<void> {
  const reject = page.getByTestId('action-reject')
  await reject.getByLabel('Reason').selectOption(reason)
  await reject.getByLabel('Remarks for the applicant').fill(remarks)
  await reject.getByRole('button', { name: 'Reject' }).click()
}

export async function assignUnit(page: Page, unit = 'RMA-G-014', area = '45'): Promise<void> {
  await page.getByTestId('assign-unit-ref').fill(unit)
  await page.getByTestId('assign-unit-area').fill(area)
  await page.getByTestId('assign-unit-submit').click()
  await expect(page.getByTestId('assigned-unit')).toContainText(unit)
}
