import { expect, test } from '@playwright/test'
import { clearDevOutbox } from '../../support/outbox'
import { scenario } from '../../support/scenarios'
import { openEntryChat, runStep } from '../../support/steps'

/**
 * NV02 (18 Nov demo, B1): the NV01 journey in Arabic. The option buttons carry the Arabic
 * labels (`label_ar`) and the card is right to left; the value button shows the Arabic brand.
 * Steps and script: docs/flow-v2/scenarios.json NV02, flow-v2-nv02.json.
 */
const entry = scenario('NV02')
const LIVE = Boolean(process.env.E2E_LIVE)

test.describe(`NV02 ${entry.title} @demo-18nov @scripted @live`, () => {
  test('Arabic option and value buttons', async ({ page, browser, request }) => {
    test.setTimeout(LIVE ? 600_000 : 240_000)
    await clearDevOutbox(request)
    const ctx = await openEntryChat(page, browser, request, entry, LIVE)
    try {
      for (const step of entry.steps ?? []) {
        if ('choose_option' in step) {
          const card = page.locator('[data-testid^="choice-card-"]').last()
          await expect(card).toHaveAttribute('dir', 'rtl')
          await expect(card.getByTestId('choice-option-fnb_cafe')).toContainText('مقهى')
        }
        if ('confirm_field' in step) {
          await expect(page.getByTestId('confirm-field-brand_name_ar').last()).toContainText(
            'بين ستريت',
          )
        }
        await test.step(JSON.stringify(step).slice(0, 80), () => runStep(ctx, step))
      }
      expect(await ctx.chat.successReference()).toMatch(/^GEO-MED-\d{6}$/)
    } finally {
      for (const context of ctx.contexts) await context.close()
    }
  })
})
