import { useCallback, useMemo, useState } from 'react'
import { useChatSession } from '../../hooks/useChatSession'
import { ChatHeader } from './ChatHeader'
import styles from './ChatPanel.module.css'
import { Composer } from './Composer'
import { ErrorBubble } from './ErrorBubble'
import { MessageList } from './MessageList'
import { NextStepStrip } from './NextStepStrip'
import { scrollToProgressStage, scrollToSelector } from './progressScroll'
import type { ProgressStageKey } from './inquiryProgress'
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
    showTyping,
    sendMessage,
    sendAction,
    isActionQueued,
    editReviewField,
    uploadDocument,
    removeDocument,
    setDocumentNumber,
    retry,
    restart,
  } = useChatSession()

  const [composerPlaceholder, setComposerPlaceholder] = useState<string | undefined>()
  const [composerFocusNonce, setComposerFocusNonce] = useState(0)
  const [highlightCardId, setHighlightCardId] = useState<string | null>(null)

  const formModeActive = useMemo(
    () => Object.values(cards).some((c) => c.card_type === 'form_mode' && c.payload.active),
    [cards],
  )

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
      isActionQueued,
    }),
    [
      sendAction,
      editReviewField,
      uploadDocument,
      removeDocument,
      setDocumentNumber,
      mallsConfirmed,
      isActionQueued,
    ],
  )

  const onStageClick = useCallback(
    (stage: ProgressStageKey) => {
      if (!draft) return
      const scrolled = scrollToProgressStage(stage, draft, cards, messages)
      if (!scrolled) return
      const confirmId =
        stage === 'company' || stage === 'brand' || stage === 'space'
          ? messages
              .flatMap((m) => m.cardIds)
              .reverse()
              .find((id) => {
                const card = cards[id]
                return (
                  card?.card_type === 'confirm_fields' &&
                  card.payload.fields.some(
                    (f) => draft?.fields.find((d) => d.key === f.key)?.group === stage,
                  )
                )
              })
          : null
      const targetId =
        confirmId ??
        (stage === 'contact'
          ? Object.values(cards).find((c) => c.card_type === 'verification')?.card_id
          : stage === 'documents'
            ? Object.values(cards).find((c) => c.card_type === 'document_upload')?.card_id
            : stage === 'review'
              ? Object.values(cards).find((c) => c.card_type === 'review')?.card_id
              : null)
      if (targetId) {
        setHighlightCardId(targetId)
        window.setTimeout(() => setHighlightCardId(null), 1200)
      }
    },
    [cards, draft, messages],
  )

  const onShowNextStep = useCallback((selector: string) => {
    scrollToSelector(selector)
  }, [])

  const errorMessage = error?.message ?? GENERIC_ERROR
  const isSessionExpired = error?.code === 'session_not_found'

  return (
    <section className={styles.panel} aria-label="Leasing assistant chat">
      <ChatHeader
        phase={phase}
        draft={draft}
        cards={cards}
        messages={messages}
        draftPanelVisible={draftPanelVisible}
        onToggleDraftPanel={onToggleDraftPanel}
        onRestart={() => void restart()}
        onStageClick={onStageClick}
      />
      <MessageList
        messages={messages}
        cards={cards}
        isStreaming={isStreaming}
        showTyping={showTyping}
        highlightCardId={highlightCardId}
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
        <NextStepStrip
          draft={draft}
          phase={phase}
          cards={cards}
          messages={messages}
          formModeActive={formModeActive}
          onShow={onShowNextStep}
        />
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
