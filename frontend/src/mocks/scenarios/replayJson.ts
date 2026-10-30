import { patchMockDraft } from '../mockStreamState'
import { advanceScenarioTurn, getActiveJsonScenario, nextScenarioTurnIndex } from './load'
import { chatRequestMatches } from './types'
import type { ChatRequest, SseEvent } from '../../types/contracts'

const STEP_DELAY_MS = 120

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const t = setTimeout(resolve, ms)
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(t)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

async function emitEvent(
  event: SseEvent,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (event.event === 'draft') {
    patchMockDraft(event.data)
  }
  if (event.event === 'token') {
    await sleep(STEP_DELAY_MS, signal)
  }
  onEvent(event)
}

export async function replayJsonScenarioChat(
  request: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const scenario = getActiveJsonScenario()
  if (!scenario?.turns?.length) {
    onEvent({ event: 'done', data: { phase: scenario?.session.draft.phase ?? 'gate' } })
    return
  }

  const idx = nextScenarioTurnIndex()
  const turn = scenario.turns[idx]
  if (!turn || !chatRequestMatches(turn.when, request)) {
    onEvent({ event: 'done', data: { phase: scenario.session.draft.phase } })
    return
  }

  if (turn.behavior === 'reject_turn_in_progress') {
    advanceScenarioTurn()
    throw Object.assign(new Error('Another turn is still in progress.'), {
      code: 'turn_in_progress',
    })
  }

  let tokenCount = 0
  for (const event of turn.events) {
    if (turn.behavior === 'abort_mid_stream' && event.event === 'token') {
      tokenCount += 1
      await emitEvent(event, onEvent, signal)
      if (tokenCount >= 1) {
        advanceScenarioTurn()
        throw Object.assign(new Error('Connection lost'), { code: 'stream_failed' })
      }
      continue
    }
    await emitEvent(event, onEvent, signal)
  }

  advanceScenarioTurn()
}
