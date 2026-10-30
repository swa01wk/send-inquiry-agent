import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'
import type { InquiryPage } from '../pages/inquiry'
import { readDoneEventCount } from './events'
import { assertSafetyInvariants, sliceEventsAfterDone } from './invariants'
import {
  assertNoDuplicateConfirmCards,
  assertPlainLanguageReply,
  assertRetractionBudget,
} from './plainLanguage'

export type AfterTurnOptions = {
  doneBefore?: number
  draftBefore?: Record<string, unknown>
}

export async function afterTurnChecks(inquiry: InquiryPage, options: AfterTurnOptions = {}) {
  const reply = await inquiry.lastReply()
  assertPlainLanguageReply(reply, inquiry.userContext())
  const events = await inquiry.events()
  assertNoDuplicateConfirmCards(events)
  assertRetractionBudget(events)

  if (process.env.E2E_LIVE && options.doneBefore !== undefined && options.draftBefore) {
    const turnEvents = sliceEventsAfterDone(events, options.doneBefore)
    const draftAfter = await inquiry.draft()
    await assertSafetyInvariants(
      inquiry.page.request,
      inquiry.sessionId!,
      turnEvents,
      options.draftBefore,
      draftAfter,
    )
  }
}

/** Live personas: capture draft/done before `say`, then run turn checks including invariants. */
export async function afterLiveTurn(
  inquiry: InquiryPage,
  doneBefore: number,
  draftBefore: Record<string, unknown>,
) {
  await afterTurnChecks(inquiry, { doneBefore, draftBefore })
}

export async function doneCount(inquiry: InquiryPage): Promise<number> {
  return readDoneEventCount(inquiry.page)
}

export async function finishA11yOnPage(page: Page, projectName: string) {
  const results = await new AxeBuilder({ page })
    .include('section[aria-label="Leasing assistant chat"]')
    .disableRules(['scrollable-region-focusable'])
    .analyze()
  const serious = results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical',
  )
  expect(serious, 'no serious axe violations').toEqual([])
  if (projectName === 'mobile') {
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    )
    expect(overflow).toBeTruthy()
  }
}

export async function finishA11y(inquiry: InquiryPage, projectName: string) {
  await finishA11yOnPage(inquiry.page, projectName)
}
