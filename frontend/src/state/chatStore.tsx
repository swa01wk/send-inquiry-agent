import {
  createContext,
  useContext,
  useReducer,
  type Dispatch,
  type ReactNode,
} from 'react'
import { draftEmpty } from '../mocks/fixtures'
import type {
  ChatRequest,
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
  pendingRetry: null,
}

export type ChatAction =
  | {
      type: 'sessionCreated'
      sessionId: string
      messages: { id: string; role: 'assistant'; text: string }[]
      cards: UiCard[]
      draft: DraftSummary
    }
  | { type: 'reset' }
  | { type: 'userMessage'; text: string; id?: string }
  | { type: 'turnStarted' }
  | { type: 'sse'; event: SseEvent }
  | { type: 'streamFailed'; error: { code: string; message: string }; pendingRetry: ChatRequest | null }

function findLastAssistantMessageId(messages: ChatMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'assistant') return messages[i].id
  }
  return null
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

function applyUiCard(state: ChatState, card: UiCard): ChatState {
  if (card.card_type === 'quick_replies') {
    return {
      ...state,
      quickReplies: card.payload.options,
    }
  }

  if (state.cards[card.card_id]) {
    return {
      ...state,
      cards: { ...state.cards, [card.card_id]: card },
    }
  }

  return {
    ...state,
    cards: { ...state.cards, [card.card_id]: card },
    messages: attachCardToMessages(state.messages, card),
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
        return { ...state, messages }
      }
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: message_id, role: 'assistant', text, cardIds: [] },
        ],
      }
    }
    case 'ui_card':
      return applyUiCard(state, event.data)
    case 'draft':
      return {
        ...state,
        draft: event.data,
        phase: event.data.phase,
      }
    case 'done':
      return {
        ...state,
        status: 'idle',
        phase: event.data.phase,
      }
    case 'error':
      return {
        ...state,
        status: 'error',
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
        error: undefined,
      }
    case 'sse':
      return applySseEvent(state, action.event)
    case 'streamFailed':
      return {
        ...state,
        status: 'error',
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
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, {
    ...initialChatState,
    draft: draftEmpty,
    phase: draftEmpty.phase,
  })

  return (
    <ChatContext.Provider value={{ state, dispatch }}>{children}</ChatContext.Provider>
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
