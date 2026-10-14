import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const TOKENS_PATH = join(process.cwd(), 'src/styles/tokens.css')

/** WCAG 2.1 relative luminance contrast ratio. */
function contrastRatio(foreground: string, background: string): number {
  const l1 = relativeLuminance(parseHex(foreground))
  const l2 = relativeLuminance(parseHex(background))
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return (lighter + 0.05) / (darker + 0.05)
}

function parseHex(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '')
  const full =
    normalized.length === 3
      ? normalized
          .split('')
          .map((c) => c + c)
          .join('')
      : normalized
  const int = Number.parseInt(full, 16)
  return [(int >> 16) & 255, (int >> 8) & 255, int & 255]
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function readTokenMap(css: string): Map<string, string> {
  const map = new Map<string, string>()
  const pattern = /(--[\w-]+):\s*(#[0-9A-Fa-f]{3,8})/g
  for (const line of css.split('\n')) {
    for (const match of line.matchAll(pattern)) {
      map.set(match[1], match[2])
    }
  }
  return map
}

/** Text colour tokens on typical surfaces (design-spec §8). */
const TEXT_ON_SURFACE: Array<[string, string]> = [
  ['--color-text', '--color-surface'],
  ['--color-text', '--color-chat-bg'],
  ['--color-text-body', '--color-surface'],
  ['--color-text-body', '--color-chat-bg'],
  ['--color-text-secondary', '--color-surface'],
  ['--color-text-muted', '--color-surface'],
  ['--color-brand', '--color-surface'],
  ['--color-accent-text', '--color-surface'],
  ['--color-success-fg', '--color-success-bg'],
  ['--color-pending-fg', '--color-pending-bg'],
  ['--color-derived-fg', '--color-derived-bg'],
  ['--color-neutral-fg', '--color-neutral-bg'],
  ['--color-disabled-fg', '--color-disabled-bg'],
  ['--color-badge-default-text', '--color-surface'],
]

describe('token contrast', () => {
  it('meets 4.5:1 for text tokens on their backgrounds', () => {
    const tokens = readTokenMap(readFileSync(TOKENS_PATH, 'utf8'))
    const failures: string[] = []

    for (const [fgVar, bgVar] of TEXT_ON_SURFACE) {
      const fg = tokens.get(fgVar)
      const bg = tokens.get(bgVar)
      if (!fg || !bg) {
        failures.push(`missing token ${fgVar} or ${bgVar}`)
        continue
      }
      const ratio = contrastRatio(fg, bg)
      if (ratio < 4.5) {
        failures.push(`${fgVar} on ${bgVar}: ${ratio.toFixed(2)}:1`)
      }
    }

    expect(failures).toEqual([])
  })
})
