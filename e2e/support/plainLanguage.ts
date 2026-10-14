import { expect } from '@playwright/test'

const BANNED = [
  'update_draft',
  'verify_cr',
  'confirm_fields',
  'send_otp',
  ' ui_event',
  'derived',
  'payload',
  'guard',
  'schema',
  'riyadh-mall-a',
  'fnb_cafe',
]

const SNAKE = /\b[a-z]+_[a-z0-9_]+\b/

export function assertPlainLanguageReply(text: string, userSoFar: string) {
  const lower = text.toLowerCase()
  for (const word of BANNED) {
    expect(lower, `reply must not contain "${word}"`).not.toContain(word)
  }
  expect(text, 'no snake_case jargon').not.toMatch(SNAKE)
  const sentences = text.split(/[.!?]+/).filter((s) => s.trim().length > 0)
  expect(sentences.length, 'at most 4 sentences').toBeLessThanOrEqual(4)
  const questions = (text.match(/\?/g) ?? []).length
  expect(questions, 'at most 2 questions').toBeLessThanOrEqual(2)

  const userLower = userSoFar.toLowerCase()
  if (!userLower.includes('coffee')) {
    expect(lower, 'no coffee before user mentions it').not.toContain('coffee')
  }
  if (!userLower.includes('kiosk')) {
    expect(lower, 'no kiosk before user mentions it').not.toContain('kiosk')
  }
  const seededMalls = ['riyadh mall a', 'jeddah mall a', 'mall of arabia', 'mall of dhahran']
  for (const name of seededMalls) {
    if (!userLower.includes(name)) {
      expect(lower, `no ${name} before user mentions it`).not.toContain(name)
    }
  }
}

export function assertNoDuplicateConfirmCards(events: CapturedLike[]) {
  const keysByCard = new Map<string, Set<string>>()
  for (const e of events) {
    if (e.event !== 'ui_card') continue
    const data = e.data as { card_type?: string; card_id?: string; payload?: { fields?: { key: string }[] } }
    if (data.card_type !== 'confirm_fields' || !data.card_id) continue
    const set = keysByCard.get(data.card_id) ?? new Set<string>()
    for (const f of data.payload?.fields ?? []) set.add(f.key)
    keysByCard.set(data.card_id, set)
  }
  const keyOwners = new Map<string, string>()
  for (const [cardId, keys] of keysByCard) {
    for (const key of keys) {
      const owner = keyOwners.get(key)
      if (owner && owner !== cardId) {
        throw new Error(`duplicate confirm card for key ${key}: ${owner} and ${cardId}`)
      }
      keyOwners.set(key, cardId)
    }
  }
}

type CapturedLike = { event: string; data: Record<string, unknown> }

export function assertRetractionBudget(events: CapturedLike[], max = 1) {
  const n = events.filter((e) => e.event === 'message_remove').length
  expect(n, `message_remove count <= ${max}`).toBeLessThanOrEqual(max)
}
