import { describe, expect, it } from 'vitest'
import { assertFeScenario } from './scenarios/validate'
import { listFeScenarioNames } from './scenarios/load'
import { feScenarioDefinitions } from './scenarios/definitions'

const jsonModules = import.meta.glob('./scenarios/*.json', { eager: true, import: 'default' })

describe('FE mock scenarios', () => {
  it('loads and validates every JSON fixture', () => {
    const names = Object.keys(jsonModules)
    expect(names.length).toBeGreaterThan(0)
    for (const [filePath, raw] of Object.entries(jsonModules)) {
      const scenario = assertFeScenario(raw, filePath)
      expect(scenario.name).toBeTruthy()
    }
  })

  it('keeps definitions in sync with committed JSON files', () => {
    const fromDisk = new Set(listFeScenarioNames())
    const fromDefs = new Set(feScenarioDefinitions.map((s) => s.name))
    expect(fromDisk).toEqual(fromDefs)
  })
})
