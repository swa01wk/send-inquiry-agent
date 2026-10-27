import { useCallback, useMemo, useState } from 'react'
import { useChatSession } from '../../hooks/useChatSession'
import { ChatHeader } from './ChatHeader'
import styles from './ChatPanel.module.css'
import { Composer } from './Composer'
import { ErrorBubble } from './ErrorBubble'
import { MessageList } from './MessageList'
import { SuggestionChips } from './SuggestionChips'

const GENERIC_ERROR = 'Sorry, something went wrong on our side. Please try again.'

interface ChatPanelProps {
  draftPanelVisible: boolean
  onToggleDraftPanel: () => void
}

export function ChatPanel({ draftPanelVisible, onToggleDraftPanel }: ChatPanelProps) {
  const {
    messages,
    cards,
    quickReplies,
    draft,
    phase,
    status,
    error,
    isStreaming,
    awaitingReply,
    sendMessage,
    sendAction,
    editReviewField,
    uploadDocument,
    removeDocument,
    setDocumentNumber,
    retry,
    restart,
  } = useChatSession()

  const [composerPlaceholder, setComposerPlaceholder] = useState<string | undefined>()
  const [composerFocusNonce, setComposerFocusNonce] = useState(0)

  const focusComposer = useCallback((placeholder: string) => {
    setComposerPlaceholder(placeholder)
    setComposerFocusNonce((n) => n + 1)
  }, [])

  const mallsConfirmed = draft?.fields.find((f) => f.key === 'malls')?.confirmed ?? false

  const cardActions = useMemo(
    () => ({
      sendAction,
      editReviewField,
      uploadDocument,
      removeDocument,
      setDocumentNumber,
      mallsConfirmed,
    }),
    [
      sendAction,
      editReviewField,
      uploadDocument,
      removeDocument,
      setDocumentNumber,
      mallsConfirmed,
    ],
  )

  const errorMessage = error?.message ?? GENERIC_ERROR
  const isSessionExpired = error?.code === 'session_not_found'

  return (
    <section className={styles.panel} aria-label="Leasing assistant chat">
      <ChatHeader
        phase={phase}
        draft={draft}
        draftPanelVisible={draftPanelVisible}
        onToggleDraftPanel={onToggleDraftPanel}
        onRestart={() => void restart()}
      />
      <MessageList
        messages={messages}
        cards={cards}
        isStreaming={isStreaming}
        showTyping={isStreaming && awaitingReply}
        cardActions={cardActions}
      />
      {status === 'error' ? (
        <div className={styles.errorWrap}>
          <ErrorBubble
            message={errorMessage}
            actionLabel={isSessionExpired ? 'Start again' : 'Retry'}
            onAction={() => (isSessionExpired ? void restart() : retry())}
          />
        </div>
      ) : null}
      <div className={styles.footer}>
        <SuggestionChips
          options={quickReplies}
          onSelect={sendMessage}
          onFocusInput={focusComposer}
          hidden={isStreaming}
        />
        <Composer
          disabled={isStreaming || status === 'error'}
          onSend={sendMessage}
          inputPlaceholder={composerPlaceholder}
          focusNonce={composerFocusNonce}
        />
      </div>
    </section>
  )
}
