import { describe, expect, it } from 'vitest'
import { confirmFieldsCardExample, quickRepliesCardExample } from '../mocks/fixtures'
import type { UiCard } from '../types/contracts'
import { chatReducer, initialChatState, reduceSse, type ChatState } from './chatStore'

describe('chatReducer', () => {
  it('accumulates token text per message_id', () => {
    let state = initialChatState
    state = chatReducer(state, { type: 'turnStarted' })
    state = reduceSse(state, {
      event: 'token',
      data: { message_id: 'm1', text: 'Hello' },
    })
    state = reduceSse(state, {
      event: 'token',
      data: { message_id: 'm1', text: ' world' },
    })
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0].text).toBe('Hello world')
  })

  it('inserts a new card on message and replaces by card_id', () => {
    let state: ChatState = {
      ...initialChatState,
      messages: [{ id: 'm1', role: 'assistant', text: 'Hi', cardIds: [] }],
    }
    state = reduceSse(state, {
      event: 'ui_card',
      data: { ...confirmFieldsCardExample, message_id: 'm1' },
    })
    expect(state.messages[0].cardIds).toEqual(['confirm-1'])
    expect(state.cards['confirm-1'].card_type).toBe('confirm_fields')

    const updated: UiCard = {
      card_id: 'confirm-1',
      card_type: 'confirm_fields',
      message_id: 'm1',
      payload: {
        title: 'Updated title',
        fields: [],
        all_confirmed: false,
      },
    }
    state = reduceSse(state, { event: 'ui_card', data: updated })
    expect(state.messages[0].cardIds).toEqual(['confirm-1'])
    const card = state.cards['confirm-1']
    expect(card.card_type === 'confirm_fields' && card.payload.title).toBe('Updated title')
  })

  it('routes quick_replies to quickReplies state', () => {
    let state = initialChatState
    state = reduceSse(state, { event: 'ui_card', data: quickRepliesCardExample })
    expect(
      quickRepliesCardExample.card_type === 'quick_replies'
        ? state.quickReplies.length
        : 0,
    ).toBe(3)
    expect(state.messages).toHaveLength(0)
  })

  it('clears quick replies at turn start', () => {
    const options =
      quickRepliesCardExample.card_type === 'quick_replies'
        ? quickRepliesCardExample.payload.options
        : []
    let state: ChatState = {
      ...initialChatState,
      quickReplies: options,
    }
    state = chatReducer(state, { type: 'turnStarted' })
    expect(state.quickReplies).toEqual([])
    expect(state.status).toBe('streaming')
  })

  it('resets status on done', () => {
    let state: ChatState = { ...initialChatState, status: 'streaming' }
    state = reduceSse(state, { event: 'done', data: { phase: 'collecting' } })
    expect(state.status).toBe('idle')
    expect(state.phase).toBe('collecting')
  })
})
