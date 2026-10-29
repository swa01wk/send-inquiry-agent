import { test } from '@playwright/test'
import { runL5AttentionFlow } from '../support/stories'

const API = 'http://127.0.0.1:8000'

/** Day 5 L5 core: stalled → escalated → drafted reminder → approved → sent once. */
test.describe('Needs attention (L5) @scripted', () => {
  test.afterEach(async ({ request }) => {
    await request.post(`${API}/api/dev/reset`) // leave the clock and data clean for others
  })

  test('the clock surfaces stuck cases and drafted reminders under the policy', async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000)
    await runL5AttentionFlow(page, request)
  })
})
