import type { ChatRequest, CreateSessionResponse, SseEvent } from '../../types/contracts'

export type FeRequestMatch =
  | { type: 'any' }
  | { type: 'message'; textIncludes?: string; textEquals?: string }
  | { type: 'action'; action: string }

export type FeTurnBehavior = 'abort_mid_stream' | 'reject_turn_in_progress'

export interface FeScenarioTurn {
  when: FeRequestMatch
  events: SseEvent[]
  behavior?: FeTurnBehavior
}

export interface FeScenario {
  name: string
  session: CreateSessionResponse
  turns?: FeScenarioTurn[]
}

export function chatRequestMatches(when: FeRequestMatch, request: ChatRequest): boolean {
  if (when.type === 'any') return true
  if (when.type === 'message') {
    if (request.type !== 'message') return false
    const text = request.text.trim()
    if (when.textEquals !== undefined && text !== when.textEquals) return false
    if (
      when.textIncludes !== undefined &&
      !text.toLowerCase().includes(when.textIncludes.toLowerCase())
    ) {
      return false
    }
    return true
  }
  if (when.type === 'action') {
    return request.type === 'action' && request.action === when.action
  }
  return false
}
