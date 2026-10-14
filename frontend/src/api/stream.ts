import { fetchEventSource } from '@microsoft/fetch-event-source'
import { API_BASE, MOCK_MODE } from '../config'
import { replayMockChat } from '../mocks/mockStream'
import type { ChatRequest, SseEvent } from '../types/contracts'

export class StreamAbortError extends Error {
  constructor() {
    super('Stream aborted')
    this.name = 'StreamAbortError'
  }
}

function parseSseMessage(eventType: string, data: string): SseEvent | null {
  if (!eventType || !data) return null
  try {
    const parsed = JSON.parse(data) as SseEvent['data']
    return { event: eventType, data: parsed } as SseEvent
  } catch {
    return null
  }
}

export type StreamOutcome = 'ok' | 'error'

export async function streamChat(
  sessionId: string,
  body: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<StreamOutcome> {
  if (MOCK_MODE) {
    await replayMockChat(body, onEvent, signal)
    return 'ok'
  }

  let sawError = false

  await fetchEventSource(`${API_BASE}/api/sessions/${sessionId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
    openWhenHidden: true,
    async onopen(res) {
      if (res.ok && res.headers.get('content-type')?.includes('text/event-stream')) {
        return
      }
      if (res.status === 429) {
        throw Object.assign(new Error('Rate limited'), { code: 'rate_limited' })
      }
      if (res.status === 404) {
        throw Object.assign(new Error('Session not found'), { code: 'session_not_found' })
      }
      let code = 'stream_failed'
      let message = 'Stream failed'
      try {
        const errBody = (await res.json()) as { error?: { code: string; message: string } }
        if (errBody.error) {
          code = errBody.error.code
          message = errBody.error.message
        }
      } catch {
        /* ignore */
      }
      throw Object.assign(new Error(message), { code })
    },
    onmessage(msg) {
      const event = parseSseMessage(msg.event, msg.data)
      if (event) {
        if (event.event === 'error') sawError = true
        onEvent(event)
      }
    },
    onerror(err) {
      if (signal.aborted) throw new StreamAbortError()
      throw err
    },
  })

  return sawError ? 'error' : 'ok'
}
