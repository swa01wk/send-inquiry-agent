/**
 * Writes frontend/src/mocks/scenarios/*.json from typed definitions.
 * Run: npx tsx scripts/generate-fe-scenarios.ts
 */
import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { feScenarioDefinitions } from '../src/mocks/scenarios/definitions'
import { assertFeScenario } from '../src/mocks/scenarios/validate'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.join(__dirname, '../src/mocks/scenarios')

for (const scenario of feScenarioDefinitions) {
  const filePath = path.join(outDir, `${scenario.name}.json`)
  assertFeScenario(scenario, filePath)
  writeFileSync(filePath, `${JSON.stringify(scenario, null, 2)}\n`)
  console.log('wrote', scenario.name)
}
