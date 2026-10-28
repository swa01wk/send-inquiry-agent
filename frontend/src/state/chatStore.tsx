import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react'
import { draftEmpty } from '../mocks/fixtures'
import type {
  ChatRequest,
  CreateSessionResponse,
  DraftSummary,
  Phase,
  QuickReplyOption,
  SseEvent,
  UiCard,
} from '../types/contracts'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  cardIds: string[]
  /** Visual divider when a follow-on inquiry starts in the same chat. */
  variant?: 'new_inquiry'
}

export type ChatStatus = 'idle' | 'streaming' | 'error'

export interface ChatState {
  sessionId: string | null
  messages: ChatMessage[]
  cards: Record<string, UiCard>
  quickReplies: QuickReplyOption[]
  draft: DraftSummary | null
  phase: Phase
  status: ChatStatus
  /** True from the start of a turn until reply text starts streaming in. */
  awaitingReply: boolean
  error?: { code: string; message: string }
  pendingRetry?: ChatRequest | null
}

export const initialChatState: ChatState = {
  sessionId: null,
  messages: [],
  cards: {},
  quickReplies: [],
  draft: null,
  phase: 'gate',
  status: 'idle',
  awaitingReply: false,
  pendingRetry: null,
}

export type ChatAction =
  | {
      type: 'sessionCreated'
      sessionId: string
      messages: { id: string; role: 'assistant' | 'user'; text: string }[]
      cards: UiCard[]
      draft: DraftSummary
    }
  | { type: 'reset' }
  | { type: 'userMessage'; text: string; id?: string }
  | { type: 'turnStarted' }
  | { type: 'sse'; event: SseEvent }
  | {
      type: 'streamFailed'
      error: { code: string; message: string }
      pendingRetry: ChatRequest | null
    }

function findLastAssistantMessageId(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'assistant') return messages[i].id
  }
  return null
}

/** Cards still in state but not linked to any message (e.g. after guard retracted a bubble). */
function orphanCardIds(state: ChatState): string[] {
  const attached = new Set(state.messages.flatMap((m) => m.cardIds))
  return Object.keys(state.cards).filter((id) => !attached.has(id))
}

function attachCardToMessages(messages: ChatMessage[], card: UiCard): ChatMessage[] {
  const targetId = card.message_id ?? findLastAssistantMessageId(messages)
  if (!targetId) return messages
  return messages.map((m) => {
    if (m.id !== targetId) return m
    if (m.cardIds.includes(card.card_id)) return m
    return { ...m, cardIds: [...m.cardIds, card.card_id] }
  })
}

function cardAttachedToMessage(messages: ChatMessage[], cardId: string): boolean {
  return messages.some((m) => m.cardIds.includes(cardId))
}

function confirmFieldKeys(card: UiCard): string[] {
  if (card.card_type !== 'confirm_fields') return []
  return card.payload.fields.map((f) => f.key)
}

function mergeOverlappingConfirmCard(state: ChatState, card: UiCard): UiCard {
  if (card.card_type !== 'confirm_fields') return card
  const incomingKeys = new Set(confirmFieldKeys(card))
  if (incomingKeys.size === 0) return card

  for (const existing of Object.values(state.cards)) {
    if (existing.card_type !== 'confirm_fields') continue
    const overlap = existing.payload.fields.some((f) => incomingKeys.has(f.key))
    if (!overlap) continue

    const byKey = new Map(existing.payload.fields.map((f) => [f.key, f]))
    for (const row of card.payload.fields) {
      byKey.set(row.key, row)
    }
    const mergedFields = [...byKey.values()]
    const allConfirmed = mergedFields.every((f) => f.confirmed)
    return {
      ...card,
      card_id: existing.card_id,
      message_id: existing.message_id ?? card.message_id,
      payload: {
        ...card.payload,
        fields: mergedFields,
        all_confirmed: allConfirmed,
      },
    }
  }
  return card
}

function applyUiCard(state: ChatState, card: UiCard): ChatState {
  if (card.card_type === 'quick_replies') {
    return {
      ...state,
      quickReplies: card.payload.options,
    }
  }

  const resolved = mergeOverlappingConfirmCard(state, card)
  const cards = { ...state.cards, [resolved.card_id]: resolved }

  if (state.cards[resolved.card_id] && cardAttachedToMessage(state.messages, resolved.card_id)) {
    return { ...state, cards }
  }

  return {
    ...state,
    cards,
    messages: attachCardToMessages(state.messages, resolved),
  }
}

function applySseEvent(state: ChatState, event: SseEvent): ChatState {
  switch (event.event) {
    case 'token': {
      const { message_id, text } = event.data
      const idx = state.messages.findIndex((m) => m.id === message_id)
      if (idx >= 0) {
        const messages = [...state.messages]
        const msg = messages[idx]
        messages[idx] = { ...msg, text: msg.text + text }
        return { ...state, messages, awaitingReply: false }
      }
      return {
        ...state,
        awaitingReply: false,
        messages: [
          ...state.messages,
          {
            id: message_id,
            role: 'assistant',
            text,
            cardIds: orphanCardIds(state),
          },
        ],
      }
    }
    case 'ui_card':
      return applyUiCard(state, event.data)
    case 'message_remove': {
      const removed = state.messages.find((m) => m.id === event.data.message_id)
      if (!removed) return state
      // Keep cards (OTP, documents, etc.) — the reply bubble is retracted, not the user's task.
      let messages = state.messages.filter((m) => m.id !== event.data.message_id)
      const orphanIds = removed.cardIds.filter((id) => state.cards[id])
      const anchorId = findLastAssistantMessageId(messages)
      if (anchorId && orphanIds.length > 0) {
        messages = messages.map((m) => {
          if (m.id !== anchorId) return m
          const cardIds = [...m.cardIds]
          for (const id of orphanIds) {
            if (!cardIds.includes(id)) cardIds.push(id)
          }
          return { ...m, cardIds }
        })
      }
      return {
        ...state,
        messages,
        awaitingReply: state.status === 'streaming',
      }
    }
    case 'draft': {
      const prevFollowOn = state.draft?.follow_on_of ?? null
      const nextFollowOn = event.data.follow_on_of ?? null
      let messages = state.messages
      if (nextFollowOn !== prevFollowOn && nextFollowOn !== null) {
        const dividerId = `divider-${nextFollowOn}`
        if (!messages.some((m) => m.id === dividerId)) {
          messages = [
            ...messages,
            {
              id: dividerId,
              role: 'assistant',
              text: '',
              cardIds: [],
              variant: 'new_inquiry',
            },
          ]
        }
      }
      return {
        ...state,
        messages,
        draft: event.data,
        phase: event.data.phase,
      }
    }
    case 'done':
      return {
        ...state,
        status: 'idle',
        awaitingReply: false,
        phase: event.data.phase,
      }
    case 'error':
      return {
        ...state,
        status: 'error',
        awaitingReply: false,
        error: event.data,
      }
    default:
      return state
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'reset':
      return { ...initialChatState }
    case 'sessionCreated': {
      let quickReplies: QuickReplyOption[] = []
      const cards: Record<string, UiCard> = {}
      let messages: ChatMessage[] = action.messages.map((m) => ({
        id: m.id,
        role: 'assistant',
        text: m.text,
        cardIds: [],
      }))

      for (const card of action.cards) {
        if (card.card_type === 'quick_replies') {
          quickReplies = card.payload.options
        } else {
          cards[card.card_id] = card
          messages = attachCardToMessages(messages, card)
        }
      }

      return {
        ...state,
        sessionId: action.sessionId,
        messages,
        cards,
        quickReplies,
        draft: action.draft,
        phase: action.draft.phase,
        status: 'idle',
        error: undefined,
        pendingRetry: null,
      }
    }
    case 'userMessage':
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: action.id ?? `user-${crypto.randomUUID()}`,
            role: 'user',
            text: action.text,
            cardIds: [],
          },
        ],
      }
    case 'turnStarted':
      return {
        ...state,
        quickReplies: [],
        status: 'streaming',
        awaitingReply: true,
        error: undefined,
      }
    case 'sse':
      return applySseEvent(state, action.event)
    case 'streamFailed':
      return {
        ...state,
        status: 'error',
        awaitingReply: false,
        error: action.error,
        pendingRetry: action.pendingRetry,
      }
    default:
      return state
  }
}

interface ChatContextValue {
  state: ChatState
  dispatch: Dispatch<ChatAction>
  initialSession: CreateSessionResponse | null
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({
  children,
  initialSession,
}: {
  children: ReactNode
  initialSession?: CreateSessionResponse | null
}) {
  const [state, dispatch] = useReducer(chatReducer, {
    ...initialChatState,
    draft: draftEmpty,
    phase: draftEmpty.phase,
  })

  return (
    <ChatContext.Provider value={{ state, dispatch, initialSession: initialSession ?? null }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChatStore(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) {
    throw new Error('useChatStore must be used within ChatProvider')
  }
  return ctx
}

/** Exported for unit tests */
export function reduceSse(state: ChatState, event: SseEvent): ChatState {
  return applySseEvent(state, event)
}
