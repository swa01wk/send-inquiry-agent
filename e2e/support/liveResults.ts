import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export type LiveScenarioResult = {
  scenario: string
  pass: boolean
  turns: number
  retractions: number
  durationMs: number
  error?: string
}

const resultsDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '../results')

export async function appendLiveResult(result: LiveScenarioResult): Promise<void> {
  const date = new Date().toISOString().slice(0, 10)
  const file = path.join(resultsDir, `live-${date}.json`)
  let existing: LiveScenarioResult[] = []
  try {
    existing = JSON.parse(await fs.readFile(file, 'utf8')) as LiveScenarioResult[]
  } catch {
    existing = []
  }
  existing.push(result)
  await fs.mkdir(resultsDir, { recursive: true })
  await fs.writeFile(file, `${JSON.stringify(existing, null, 2)}\n`)
}
