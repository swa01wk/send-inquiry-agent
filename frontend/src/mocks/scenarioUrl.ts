const DEFAULT_SCENARIO = 'demo'

/** Mock-only: `?scenario=<name>` on the inquiry page (INT uses `e2eScenario` instead). */
export function mockScenarioFromUrl(): string {
  if (typeof window === 'undefined') return DEFAULT_SCENARIO
  const raw = new URLSearchParams(window.location.search).get('scenario')?.trim()
  return raw || DEFAULT_SCENARIO
}

export function isDemoScenario(name: string): boolean {
  return name === 'demo' || name === ''
}
