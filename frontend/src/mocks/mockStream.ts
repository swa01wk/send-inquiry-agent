import { getActiveScenarioId } from './scenarios/load'
import { replayDemoChat } from './scenarios/demo'
import { replayJsonScenarioChat } from './scenarios/replayJson'
import type { ChatRequest, SseEvent } from '../types/contracts'

export async function replayMockChat(
  request: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (getActiveScenarioId() === 'demo') {
    await replayDemoChat(request, onEvent, signal)
    return
  }
  await replayJsonScenarioChat(request, onEvent, signal)
}
