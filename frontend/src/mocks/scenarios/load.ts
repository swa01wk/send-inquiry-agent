import { isDemoScenario, mockScenarioFromUrl } from '../scenarioUrl'
import { assertFeScenario } from './validate'
import type { FeScenario } from './types'

const jsonModules = import.meta.glob('./*.json', { eager: true, import: 'default' })

const byName = new Map<string, FeScenario>()

for (const [filePath, raw] of Object.entries(jsonModules)) {
  const scenario = assertFeScenario(raw, filePath)
  byName.set(scenario.name, scenario)
}

let activeScenarioId: string | null = null
let turnIndex = 0

export function listFeScenarioNames(): string[] {
  return [...byName.keys()].sort()
}

export function getFeScenario(name: string): FeScenario | undefined {
  return byName.get(name)
}

/** Resolved scenario for the current page URL (demo when missing or unknown). */
export function resolveActiveFeScenario(): { id: string; json: FeScenario | null } {
  const requested = mockScenarioFromUrl()
  if (isDemoScenario(requested)) {
    return { id: 'demo', json: null }
  }
  const json = byName.get(requested)
  if (!json) {
    return { id: 'demo', json: null }
  }
  return { id: requested, json }
}

export function setActiveScenarioFromUrl(): void {
  const { id, json } = resolveActiveFeScenario()
  activeScenarioId = id
  turnIndex = 0
  if (json) {
    // keep mock draft in sync when session loads
    void json
  }
}

export function getActiveScenarioId(): string {
  if (activeScenarioId === null) {
    setActiveScenarioFromUrl()
  }
  return activeScenarioId ?? 'demo'
}

export function getActiveJsonScenario(): FeScenario | null {
  const { json } = resolveActiveFeScenario()
  return json
}

export function resetScenarioTurnState(): void {
  turnIndex = 0
  setActiveScenarioFromUrl()
}

export function nextScenarioTurnIndex(): number {
  return turnIndex
}

export function advanceScenarioTurn(): void {
  turnIndex += 1
}
