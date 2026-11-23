import { expect, test } from '@playwright/test'
import { expectFlowPath } from '../../support/flowV2'
import { clearDevOutbox } from '../../support/outbox'
import { scenario } from '../../support/scenarios'
import { openEntryChat, runStep } from '../../support/steps'

/**
 * NV01 (18 Nov demo, B1): a Media unit; "coffee and breakfast" gives two category buttons;
 * a tap sets the category; the Arabic brand name is confirmed with its value button; through
 * to Submit with a GEO-MED reference. Steps and script: docs/flow-v2/scenarios.json NV01,
 * backend/tests/e2e_scripts/flow-v2-nv01.json (AGENT-DET runs the same entry, and checks
 * the case's final level is the RPLM Media).
 */
const entry = scenario('NV01')
const LIVE = Boolean(process.env.E2E_LIVE)

test.describe(`NV01 ${entry.title} @demo-18nov @scripted @live`, () => {
  test('media inquiry with category and value buttons', async ({ page, browser, request }) => {
    test.setTimeout(LIVE ? 600_000 : 240_000)
    await clearDevOutbox(request)
    const ctx = await openEntryChat(page, browser, request, entry, LIVE)
    try {
      for (const step of entry.steps ?? []) {
        if ('choose_option' in step) {
          // "coffee and breakfast" offers the Food & Beverage group's two categories.
          await expect(page.locator('[data-testid^="choice-option-"]')).toHaveCount(2)
        }
        await test.step(JSON.stringify(step).slice(0, 80), () => runStep(ctx, step))
      }
      await expect(page.getByRole('button', { name: 'Looks right' })).toHaveCount(0)
      expect(await ctx.chat.successReference()).toMatch(/^GEO-MED-\d{6}$/)
      await expectFlowPath(request, ctx.chat.sessionId!, entry.chart_paths, entry.not_path ?? [])
    } finally {
      for (const context of ctx.contexts) await context.close()
    }
  })
})
