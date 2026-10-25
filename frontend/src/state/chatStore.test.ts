import { describe, expect, it } from 'vitest'
import {
  confirmFieldsCardExample,
  verificationCardExample,
  quickRepliesCardExample,
} from '../mocks/fixtures'
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

describe('streaming and retraction', () => {
  it('shows typing until the first token, then hides it', () => {
    let state = chatReducer(initialChatState, { type: 'turnStarted' })
    expect(state.awaitingReply).toBe(true)
    state = reduceSse(state, { event: 'token', data: { message_id: 'm1', text: 'Hi' } })
    expect(state.awaitingReply).toBe(false)
    state = reduceSse(state, { event: 'done', data: { phase: 'gate' } })
    expect(state.awaitingReply).toBe(false)
    expect(state.status).toBe('idle')
  })

  it('removes a retracted reply and waits for the replacement', () => {
    let state = chatReducer(initialChatState, { type: 'turnStarted' })
    state = reduceSse(state, { event: 'token', data: { message_id: 'bad', text: 'Submitted!' } })
    state = reduceSse(state, { event: 'message_remove', data: { message_id: 'bad' } })
    expect(state.messages.find((m) => m.id === 'bad')).toBeUndefined()
    expect(state.awaitingReply).toBe(true)
    state = reduceSse(state, { event: 'token', data: { message_id: 'good', text: 'Not yet' } })
    expect(state.messages.map((m) => m.id)).toEqual(['good'])
  })

  it('keeps cards when a reply bubble is retracted and reattaches them', () => {
    let state: ChatState = {
      ...initialChatState,
      status: 'streaming',
      messages: [
        { id: 'keep', role: 'assistant', text: 'Earlier', cardIds: [] },
        { id: 'bad', role: 'assistant', text: 'Wrong claim', cardIds: ['otp-1'] },
      ],
      cards: { 'otp-1': { ...verificationCardExample, card_id: 'otp-1', message_id: 'bad' } },
    }
    state = reduceSse(state, { event: 'message_remove', data: { message_id: 'bad' } })
    expect(state.cards['otp-1']).toBeDefined()
    expect(state.messages.find((m) => m.id === 'bad')).toBeUndefined()
    expect(state.messages.find((m) => m.id === 'keep')?.cardIds).toEqual(['otp-1'])
  })

  it('ignores removal of an unknown message', () => {
    const state = reduceSse(initialChatState, {
      event: 'message_remove',
      data: { message_id: 'nope' },
    })
    expect(state).toBe(initialChatState)
  })

  it('keeps an updated card on its original message when message_id changes', () => {
    let state: ChatState = {
      ...initialChatState,
      messages: [
        { id: 'm1', role: 'assistant', text: 'First', cardIds: ['confirm-1'] },
        { id: 'm2', role: 'assistant', text: 'Second', cardIds: [] },
      ],
      cards: {
        'confirm-1': {
          ...confirmFieldsCardExample,
          card_id: 'confirm-1',
          message_id: 'm1',
        },
      },
    }
    state = reduceSse(state, {
      event: 'ui_card',
      data: {
        card_id: 'confirm-1',
        card_type: 'confirm_fields',
        message_id: 'm2',
        payload: {
          title: 'Updated on wrong message',
          fields: [],
          all_confirmed: false,
        },
      },
    })
    expect(state.messages.find((m) => m.id === 'm1')?.cardIds).toEqual(['confirm-1'])
    expect(state.messages.find((m) => m.id === 'm2')?.cardIds).toEqual([])
  })

  it('reattaches an orphaned card to the next assistant message', () => {
    let state: ChatState = {
      ...initialChatState,
      status: 'streaming',
      messages: [
        { id: 'keep', role: 'assistant', text: 'Earlier', cardIds: [] },
        { id: 'bad', role: 'assistant', text: 'Retracted', cardIds: ['otp-1'] },
      ],
      cards: { 'otp-1': { ...verificationCardExample, card_id: 'otp-1', message_id: 'bad' } },
    }
    state = reduceSse(state, { event: 'message_remove', data: { message_id: 'bad' } })
    expect(state.messages.find((m) => m.id === 'keep')?.cardIds).toEqual(['otp-1'])

    state = reduceSse(state, {
      event: 'ui_card',
      data: { ...verificationCardExample, card_id: 'otp-1', message_id: 'bad' },
    })
    expect(state.messages.find((m) => m.id === 'keep')?.cardIds).toEqual(['otp-1'])
    expect(state.messages.filter((m) => m.cardIds.includes('otp-1'))).toHaveLength(1)
  })
})
