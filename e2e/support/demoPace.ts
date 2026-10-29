import type { Page } from '@playwright/test'

const BANNER_ID = '__e2e_demo_caption'

export type DemoBeat = (page: Page) => Promise<void>

export function demoPauseMs(): number {
  const ms = Number(process.env.E2E_DEMO_PAUSE_MS ?? 0)
  return Number.isFinite(ms) && ms > 0 ? ms : 0
}

export function demoStepMode(): boolean {
  return process.env.E2E_DEMO_STEP === '1'
}

/** Scale the demo test timeout when pauses are enabled (headed rehearsal). */
export function demoTestTimeoutMs(): number {
  return demoPauseMs() > 0 ? 45 * 60_000 : 15 * 60_000
}

/** Fixed overlay with the section name; removed when the next caption runs. */
export async function caption(page: Page, text: string): Promise<void> {
  const ms = demoPauseMs()
  if (ms <= 0) return

  await page.evaluate(
    ({ id, label }) => {
      document.getElementById(id)?.remove()
      const el = document.createElement('div')
      el.id = id
      el.textContent = label
      Object.assign(el.style, {
        position: 'fixed',
        top: '0',
        left: '0',
        right: '0',
        zIndex: '2147483647',
        pointerEvents: 'none',
        padding: '12px 20px',
        font: '600 18px/1.3 system-ui, sans-serif',
        color: '#fff',
        background: 'rgba(15, 23, 42, 0.92)',
        boxShadow: '0 2px 12px rgba(0,0,0,0.25)',
      })
      document.body.appendChild(el)
    },
    { id: BANNER_ID, label: text },
  )

  await page.waitForTimeout(ms)

  if (demoStepMode()) {
    await page.pause()
  }
}

/** Brief pause after a bot reply or card so headed demos can be read. */
export async function beat(page: Page): Promise<void> {
  const ms = demoPauseMs()
  if (ms <= 0) return
  await page.waitForTimeout(Math.floor(ms / 2))
}
