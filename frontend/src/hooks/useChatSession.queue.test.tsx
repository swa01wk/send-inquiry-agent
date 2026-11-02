import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import * as client from '../api/client'
import * as stream from '../api/stream'
import { ChatProvider } from '../state/chatStore'
import { useChatSession } from './useChatSession'

function wrapper({ children }: { children: ReactNode }) {
  return <ChatProvider>{children}</ChatProvider>
}

describe('useChatSession action queue', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(client, 'createSession').mockResolvedValue({
      session_id: 'sess-q',
      messages: [],
      cards: [],
      draft: {
        phase: 'gate',
        fields: [],
        documents: [],
        checks: {
          required_filled: 0,
          required_total: 11,
          unconfirmed: 0,
          email_verified: false,
          mobile_verified: false,
          contact_verified: false,
          required_docs_uploaded: 0,
          required_docs_total: 2,
          terms_accepted: false,
          remaining: ['cr'],
          next_step: 'cr',
        },
        can_submit: false,
        changed_keys: [],
        follow_on_of: null,
      },
    })
  })

  it('queues an action while streaming and sends it after done', async () => {
    let resolveStream: (() => void) | null = null
    const streamChat = vi
      .spyOn(stream, 'streamChat')
      .mockImplementation(async (_sessionId, body, onEvent) => {
        if (body.type === 'message') {
          await new Promise<void>((resolve) => {
            resolveStream = resolve
          })
        }
        onEvent({ event: 'done', data: { phase: 'gate' } })
        return 'ok'
      })

    const { result } = renderHook(() => useChatSession(), { wrapper })
    await waitFor(() => expect(result.current.sessionId).toBe('sess-q'))

    act(() => {
      result.current.sendMessage('hello')
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    act(() => {
      result.current.sendAction('verify_email', { token: 'tok-1' })
      result.current.sendAction('verify_email', { token: 'tok-1' })
    })
    expect(result.current.isActionQueued('verify_email', { token: 'tok-1' })).toBe(true)

    await act(async () => {
      resolveStream?.()
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(false))
    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(2))
  })

  it('clears the action queue when the stream fails', async () => {
    let resolveStream: (() => void) | null = null
    vi.spyOn(stream, 'streamChat').mockImplementation(async (_sessionId, body, onEvent) => {
      if (body.type === 'message') {
        await new Promise<void>((resolve) => {
          resolveStream = resolve
        })
        onEvent({ event: 'error', data: { code: 'agent_error', message: 'fail' } })
        return 'error'
      }
      return 'ok'
    })

    const { result } = renderHook(() => useChatSession(), { wrapper })
    await waitFor(() => expect(result.current.sessionId).toBe('sess-q'))

    act(() => {
      result.current.sendMessage('hello')
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    act(() => {
      result.current.sendAction('verify_email', { token: 'tok-1' })
    })
    expect(result.current.isActionQueued('verify_email', { token: 'tok-1' })).toBe(true)

    await act(async () => {
      resolveStream?.()
    })
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.isActionQueued('verify_email', { token: 'tok-1' })).toBe(false)
  })
})
