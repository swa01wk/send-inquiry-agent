import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ChatMessage } from '../../state/chatStore'
import { MessageList } from './MessageList'

describe('MessageList', () => {
  it('shows avatar only on the first bot message of a run', () => {
    const messages: ChatMessage[] = [
      { id: 'u1', role: 'user', text: 'Hi', cardIds: [] },
      { id: 'b1', role: 'assistant', text: 'Hello', cardIds: [] },
      { id: 'b2', role: 'assistant', text: 'More', cardIds: [] },
    ]

    const cardActions = {
      sendAction: () => undefined,
      editReviewField: async () => true,
      uploadDocument: async () => undefined,
      removeDocument: async () => undefined,
      setDocumentNumber: () => undefined,
      mallsConfirmed: false,
    }
    render(
      <MessageList messages={messages} cards={{}} isStreaming={false} cardActions={cardActions} />,
    )

    expect(screen.getAllByTestId('bot-avatar')).toHaveLength(1)
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getAllByTestId('bot-bubble-text').map((el) => el.textContent)).toContain('More')
  })

  it('renders no bubble for a whitespace-only assistant message', () => {
    const messages: ChatMessage[] = [
      { id: 'b1', role: 'assistant', text: 'Hello', cardIds: [] },
      { id: 'u1', role: 'user', text: 'Can I talk to someone?', cardIds: [] },
      { id: 'b2', role: 'assistant', text: '\n\n', cardIds: [] },
    ]
    const cardActions = {
      sendAction: () => undefined,
      editReviewField: async () => true,
      uploadDocument: async () => undefined,
      removeDocument: async () => undefined,
      setDocumentNumber: () => undefined,
      mallsConfirmed: false,
    }
    render(
      <MessageList messages={messages} cards={{}} isStreaming={false} cardActions={cardActions} />,
    )

    expect(screen.getAllByTestId('bot-bubble-text')).toHaveLength(1)
  })
})
