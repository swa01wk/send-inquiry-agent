import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChatCardActions } from '../cards/cardActions'
import type { ChatMessage } from '../../state/chatStore'
import type { UiCard } from '../../types/contracts'
import { BotBubble } from './BotBubble'
import { CardSlot } from './CardSlot'
import styles from './MessageList.module.css'
import { TypingIndicator } from './TypingIndicator'
import { UserBubble } from './UserBubble'

interface MessageListProps {
  messages: ChatMessage[]
  cards: Record<string, UiCard>
  isStreaming: boolean
  /** Show the typing dots (streaming, but no reply text yet). */
  showTyping?: boolean
  cardActions: ChatCardActions
}

export function MessageList({
  messages,
  cards,
  isStreaming,
  showTyping = isStreaming,
  cardActions,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const seenCardIds = useRef<Set<string>>(new Set())
  const [focusCardId, setFocusCardId] = useState<string | null>(null)
  const [liveAnnouncement, setLiveAnnouncement] = useState('')

  const orderedCardIds = useMemo(
    () => messages.flatMap((m) => m.cardIds).filter((id) => cards[id]),
    [messages, cards],
  )

  useEffect(() => {
    for (const id of orderedCardIds) {
      if (!seenCardIds.current.has(id)) {
        seenCardIds.current.add(id)
        setFocusCardId(id)
      }
    }
  }, [orderedCardIds])

  useEffect(() => {
    if (isStreaming) return
    const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant' && m.text)
    if (lastAssistant?.text) {
      setLiveAnnouncement(lastAssistant.text)
    }
  }, [messages, isStreaming])

  useEffect(() => {
    const el = bottomRef.current
    if (el && typeof el.scrollIntoView === 'function') {
      // Instant while text streams in (smooth scrolling on every token stutters).
      el.scrollIntoView({ behavior: isStreaming ? 'auto' : 'smooth', block: 'end' })
      return
    }
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, isStreaming, cards])

  return (
    <div ref={listRef} className={styles.list}>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {liveAnnouncement}
      </div>
      {messages.map((message, index) => {
        const prev = messages[index - 1]
        if (message.role === 'user') {
          return (
            <div key={message.id} className={styles.block}>
              <UserBubble text={message.text} />
            </div>
          )
        }

        const showAvatar = !prev || prev.role !== 'assistant'
        const cardIds = message.cardIds.filter((id) => cards[id])

        return (
          <div key={message.id} className={styles.block}>
            {/* Whitespace-only text (a newline before a tool call) gets no bubble. */}
            {message.text.trim() ? <BotBubble text={message.text} showAvatar={showAvatar} /> : null}
            {cardIds.length > 0 ? (
              <div className={styles.cards}>
                {cardIds.map((cardId) => (
                  <CardSlot
                    key={cardId}
                    card={cards[cardId]}
                    actions={cardActions}
                    focusOnMount={cardId === focusCardId}
                  />
                ))}
              </div>
            ) : null}
          </div>
        )
      })}
      {showTyping ? <TypingIndicator /> : null}
      <div ref={bottomRef} />
    </div>
  )
}
