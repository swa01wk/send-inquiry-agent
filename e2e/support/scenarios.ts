import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * The flow v2 catalogue (docs/flow-v2/scenarios.json), the one definition every layer reads
 * (flow v2 test plan §2): AGENT-DET (pytest), AGENT-LIVE (eval) and these Playwright specs.
 */
export type CatalogueStep = Record<string, unknown>

export interface CatalogueEntry {
  id: string
  title: string
  chart_paths: string[][]
  not_path?: string[]
  contexts?: string[]
  steps?: CatalogueStep[]
  expect?: Record<string, unknown>
  layers?: { int?: boolean; e2e_live?: boolean }
  cc_dictation?: Record<string, string>
}

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), '../..')
const catalogue = JSON.parse(
  readFileSync(path.join(repoRoot, 'docs/flow-v2/scenarios.json'), 'utf-8'),
) as { scenarios: CatalogueEntry[]; personas?: Record<string, { email?: string }> }

export function scenario(id: string): CatalogueEntry {
  const entry = catalogue.scenarios.find((s) => s.id === id)
  if (!entry) throw new Error(`scenario ${id} not in the catalogue`)
  return entry
}

export function persona(key: string): { email?: string } {
  return catalogue.personas?.[key] ?? {}
}

/** The scripted model for a scenario (backend/tests/e2e_scripts/flow-v2-<id>.json). */
export function scriptFor(id: string): string {
  return `flow-v2-${id.toLowerCase()}`
}
