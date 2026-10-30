import type { FeRequestMatch, FeScenario, FeScenarioTurn, FeTurnBehavior } from './types'

const SSE_EVENTS = new Set(['token', 'ui_card', 'message_remove', 'draft', 'done', 'error'])
const BEHAVIORS = new Set<FeTurnBehavior>(['abort_mid_stream', 'reject_turn_in_progress'])

function path(filePath: string, suffix: string): string {
  return `${filePath}: ${suffix}`
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function expectString(
  obj: Record<string, unknown>,
  key: string,
  filePath: string,
  at: string,
): string {
  const v = obj[key]
  if (typeof v !== 'string' || !v.trim()) {
    throw new Error(path(filePath, `${at}.${key} must be a non-empty string`))
  }
  return v
}

function validateRequestMatch(raw: unknown, filePath: string, at: string): FeRequestMatch {
  if (!isRecord(raw)) throw new Error(path(filePath, `${at} must be an object`))
  const type = expectString(raw, 'type', filePath, at)
  if (type === 'any') return { type: 'any' }
  if (type === 'message') {
    const match: FeRequestMatch = { type: 'message' }
    if (raw.textIncludes !== undefined) {
      if (typeof raw.textIncludes !== 'string') {
        throw new Error(path(filePath, `${at}.textIncludes must be a string`))
      }
      match.textIncludes = raw.textIncludes
    }
    if (raw.textEquals !== undefined) {
      if (typeof raw.textEquals !== 'string') {
        throw new Error(path(filePath, `${at}.textEquals must be a string`))
      }
      match.textEquals = raw.textEquals
    }
    return match
  }
  if (type === 'action') {
    return { type: 'action', action: expectString(raw, 'action', filePath, at) }
  }
  throw new Error(path(filePath, `${at}.type must be any, message, or action`))
}

function validateSseEvent(raw: unknown, filePath: string, at: string): void {
  if (!isRecord(raw)) throw new Error(path(filePath, `${at} must be an object`))
  const event = expectString(raw, 'event', filePath, at)
  if (!SSE_EVENTS.has(event)) {
    throw new Error(path(filePath, `${at}.event must be one of ${[...SSE_EVENTS].join(', ')}`))
  }
  if (!isRecord(raw.data)) throw new Error(path(filePath, `${at}.data must be an object`))
  const data = raw.data
  switch (event) {
    case 'token':
      expectString(data, 'message_id', filePath, `${at}.data`)
      if (typeof data.text !== 'string') {
        throw new Error(path(filePath, `${at}.data.text must be a string`))
      }
      break
    case 'message_remove':
      expectString(data, 'message_id', filePath, `${at}.data`)
      break
    case 'done':
      if (typeof data.phase !== 'string') {
        throw new Error(path(filePath, `${at}.data.phase must be a string`))
      }
      break
    case 'error':
      expectString(data, 'code', filePath, `${at}.data`)
      expectString(data, 'message', filePath, `${at}.data`)
      break
    case 'ui_card':
      expectString(data, 'card_id', filePath, `${at}.data`)
      expectString(data, 'card_type', filePath, `${at}.data`)
      if (!isRecord(data.payload)) {
        throw new Error(path(filePath, `${at}.data.payload must be an object`))
      }
      break
    case 'draft':
      if (!Array.isArray(data.fields) || !Array.isArray(data.documents)) {
        throw new Error(
          path(filePath, `${at}.data must look like DraftSummary (fields, documents)`),
        )
      }
      if (typeof data.phase !== 'string' || typeof data.can_submit !== 'boolean') {
        throw new Error(path(filePath, `${at}.data must include phase and can_submit`))
      }
      break
    default:
      break
  }
}

function validateTurn(raw: unknown, filePath: string, index: number): FeScenarioTurn {
  const at = `turns[${index}]`
  if (!isRecord(raw)) throw new Error(path(filePath, `${at} must be an object`))
  const when = validateRequestMatch(raw.when, filePath, `${at}.when`)
  if (!Array.isArray(raw.events)) {
    throw new Error(path(filePath, `${at}.events must be an array`))
  }
  raw.events.forEach((ev, i) => validateSseEvent(ev, filePath, `${at}.events[${i}]`))
  if (raw.behavior !== undefined) {
    if (typeof raw.behavior !== 'string' || !BEHAVIORS.has(raw.behavior as FeTurnBehavior)) {
      throw new Error(
        path(filePath, `${at}.behavior must be abort_mid_stream or reject_turn_in_progress`),
      )
    }
  }
  return {
    when,
    events: raw.events as FeScenarioTurn['events'],
    behavior: raw.behavior as FeTurnBehavior | undefined,
  }
}

function validateSession(raw: unknown, filePath: string): FeScenario['session'] {
  if (!isRecord(raw)) throw new Error(path(filePath, 'session must be an object'))
  expectString(raw, 'session_id', filePath, 'session')
  if (!Array.isArray(raw.messages)) {
    throw new Error(path(filePath, 'session.messages must be an array'))
  }
  if (!Array.isArray(raw.cards)) {
    throw new Error(path(filePath, 'session.cards must be an array'))
  }
  if (!isRecord(raw.draft)) {
    throw new Error(path(filePath, 'session.draft must be an object'))
  }
  return raw as unknown as FeScenario['session']
}

/** Runtime check for JSON fixtures; throws with file path and field on failure. */
export function assertFeScenario(raw: unknown, filePath: string): FeScenario {
  if (!isRecord(raw)) throw new Error(path(filePath, 'root must be an object'))
  const name = expectString(raw, 'name', filePath, 'root')
  const stem = filePath.replace(/^.*\//, '').replace(/\.json$/, '')
  if (name !== stem) {
    throw new Error(path(filePath, `name "${name}" must match filename stem "${stem}"`))
  }
  const session = validateSession(raw.session, filePath)
  let turns: FeScenarioTurn[] | undefined
  if (raw.turns !== undefined) {
    if (!Array.isArray(raw.turns)) throw new Error(path(filePath, 'turns must be an array'))
    turns = raw.turns.map((t, i) => validateTurn(t, filePath, i))
  }
  return { name, session, turns }
}
