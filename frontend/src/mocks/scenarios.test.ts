import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { assertFeScenario } from './scenarios/validate'
import { feScenarioDefinitions } from './scenarios/definitions'

const topLevelJsonModules = import.meta.glob('./scenarios/*.json', {
  eager: true,
  import: 'default',
})
const parityJsonModules = import.meta.glob('./scenarios/parity/*.json', {
  eager: true,
  import: 'default',
})

const mocksDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(mocksDir, '../../..')

describe('FE mock scenarios', () => {
  it('loads and validates every JSON fixture', () => {
    const modules = { ...topLevelJsonModules, ...parityJsonModules }
    const names = Object.keys(modules)
    expect(names.length).toBeGreaterThan(0)
    for (const [filePath, raw] of Object.entries(modules)) {
      const scenario = assertFeScenario(raw, filePath)
      expect(scenario.name).toBeTruthy()
    }
  })

  it('keeps definitions in sync with committed top-level JSON files', () => {
    const fromDisk = new Set(
      Object.entries(topLevelJsonModules).map(
        ([filePath, raw]) => assertFeScenario(raw, filePath).name,
      ),
    )
    const fromDefs = new Set(feScenarioDefinitions.map((s) => s.name))
    expect(fromDisk).toEqual(fromDefs)
  })

  it('every parity JSON fixture has a matching backend golden transcript', () => {
    const parityDir = path.join(mocksDir, 'scenarios/parity')
    const goldenDir = path.join(repoRoot, 'backend/tests/parity/golden')
    const parityFiles = fs.readdirSync(parityDir).filter((name) => name.endsWith('.json'))
    expect(parityFiles.length).toBeGreaterThan(0)
    for (const file of parityFiles) {
      const stem = file.replace(/\.json$/, '')
      expect(fs.existsSync(path.join(goldenDir, `${stem}.jsonl`))).toBe(true)
    }
  })
})
