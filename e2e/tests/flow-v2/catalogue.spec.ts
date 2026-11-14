import { expect, test } from '@playwright/test'
import { expectFlowPath } from '../../support/flowV2'
import { clearDevOutbox, fetchDevOutbox } from '../../support/outbox'
import { scenario } from '../../support/scenarios'
import { openEntryChat, runStep } from '../../support/steps'

/**
 * Flow v2 INT and E2E-LIVE (test plan §6): the public intake (S1–S17) and the call-centre
 * stories (CC1–CC3) from docs/flow-v2/scenarios.json, step by step in the browser, then the
 * chart path. Scripted runs use backend/tests/e2e_scripts/flow-v2-<id>.json, the same scripts
 * AGENT-DET runs (backend/tests/flow_v2/test_catalogue.py); live runs use the real model.
 * The after-submit stories (S18–S24) have their own specs in this folder.
 */
const IDS = [...Array.from({ length: 17 }, (_, i) => `S${i + 1}`), 'CC1', 'CC2', 'CC3']
const LIVE = Boolean(process.env.E2E_LIVE)

for (const id of IDS) {
  const entry = scenario(id)
  const tags = ['@flow-v2', '@scripted', ...(entry.layers?.e2e_live ? ['@live'] : [])]
  test.describe(`${id} ${entry.title} ${tags.join(' ')}`, () => {
    test(`follows its chart path`, async ({ page, browser, request }) => {
      test.setTimeout(LIVE ? 600_000 : 240_000)
      await clearDevOutbox(request)
      const ctx = await openEntryChat(page, browser, request, entry, LIVE)
      try {
        for (const step of entry.steps ?? []) {
          await test.step(JSON.stringify(step).slice(0, 80), () => runStep(ctx, step))
        }
        const sessionId = ctx.chat.sessionId
        expect(sessionId, 'chat session').toBeTruthy()
        await expectFlowPath(request, sessionId!, entry.chart_paths, entry.not_path ?? [])
        const outbox = (entry.expect?.outbox as string[] | undefined) ?? []
        if ((entry.contexts ?? []).includes('call_centre') && outbox.length) {
          const sent = new Set((await fetchDevOutbox(request)).map((m) => m.template))
          for (const template of outbox) expect(sent, `outbox ${template}`).toContain(template)
        }
      } finally {
        for (const context of ctx.contexts) await context.close()
      }
    })
  })
}
