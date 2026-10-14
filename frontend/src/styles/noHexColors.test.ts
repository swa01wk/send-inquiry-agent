import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const HEX_COLOR = /#[0-9A-Fa-f]{3,8}\b/g

const SRC_ROOT = join(process.cwd(), 'src')
const ALLOWED = new Set(['styles/tokens.css'])

function listSourceFiles(dir: string): string[] {
  const entries = readdirSync(dir)
  const files: string[] = []
  for (const entry of entries) {
    const full = join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      files.push(...listSourceFiles(full))
      continue
    }
    if (/\.(ts|tsx|css)$/.test(entry)) {
      files.push(full)
    }
  }
  return files
}

describe('design tokens', () => {
  it('keeps hex colours only in tokens.css', () => {
    const violations: string[] = []

    for (const file of listSourceFiles(SRC_ROOT)) {
      const rel = relative(SRC_ROOT, file)
      if (ALLOWED.has(rel)) {
        continue
      }
      const content = readFileSync(file, 'utf8')
      const matches = content.match(HEX_COLOR)
      if (matches?.length) {
        violations.push(`${rel}: ${matches.join(', ')}`)
      }
    }

    expect(violations).toEqual([])
  })
})
