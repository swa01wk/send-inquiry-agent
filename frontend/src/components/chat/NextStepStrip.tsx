import { useEffect, useRef, useState } from 'react'
import type { DraftSummary } from '../../types/contracts'
import type { ChatMessage } from '../../state/chatStore'
import type { UiCard } from '../../types/contracts'
import { NEXT_STEP_STRIP_COPY, nextStepStripStep, stageScrollTarget } from './inquiryProgress'
import styles from './NextStepStrip.module.css'

interface NextStepStripProps {
  draft: DraftSummary | null
  phase: DraftSummary['phase']
  cards: Record<string, UiCard>
  messages: ChatMessage[]
  assistedIntake?: boolean
  formModeActive?: boolean
  onShow: (selector: string) => void
}

function scrollSelectorForStep(
  step: ReturnType<typeof nextStepStripStep>,
  draft: DraftSummary,
  cards: Record<string, UiCard>,
  messages: ChatMessage[],
): string | null {
  if (!step) return null
  if (step === 'verify_email' || step === 'verify_mobile') {
    const target = stageScrollTarget('contact', draft, cards, messages)
    return target?.kind === 'selector' ? target.selector : null
  }
  if (step === 'documents') {
    const target = stageScrollTarget('documents', draft, cards, messages)
    return target?.kind === 'selector' ? target.selector : null
  }
  const target = stageScrollTarget('review', draft, cards, messages)
  return target?.kind === 'selector' ? target.selector : null
}

export function shouldShowNextStepStrip({
  draft,
  phase,
  assistedIntake,
  formModeActive,
}: {
  draft: DraftSummary | null
  phase: DraftSummary['phase']
  assistedIntake?: boolean
  formModeActive?: boolean
}): boolean {
  if (!draft || phase === 'submitted' || assistedIntake || formModeActive) return false
  const step = nextStepStripStep(draft.checks.next_step)
  if (!step) return false
  if (draft.checks.next_step === 'cr' || draft.checks.next_step === 'fields') return false
  return true
}

export function NextStepStrip({
  draft,
  phase,
  cards,
  messages,
  assistedIntake = false,
  formModeActive = false,
  onShow,
}: NextStepStripProps) {
  const step = draft ? nextStepStripStep(draft.checks.next_step) : null
  const selector = step && draft ? scrollSelectorForStep(step, draft, cards, messages) : null
  const [cardInView, setCardInView] = useState(true)
  const [announced, setAnnounced] = useState('')
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    observerRef.current?.disconnect()
    if (!selector) {
      setCardInView(true)
      return
    }
    const el = document.querySelector(selector)
    if (!el) {
      setCardInView(false)
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        setCardInView(entry?.isIntersecting ?? false)
      },
      { root: null, threshold: 0.35 },
    )
    observer.observe(el)
    observerRef.current = observer
    return () => observer.disconnect()
  }, [selector, cards, messages])

  const visible =
    shouldShowNextStepStrip({ draft, phase, assistedIntake, formModeActive }) &&
    selector &&
    !cardInView &&
    step

  useEffect(() => {
    if (visible && step) {
      setAnnounced(NEXT_STEP_STRIP_COPY[step])
    }
  }, [visible, step])

  if (!visible || !step) return null

  return (
    <div className={styles.strip} data-testid="next-step-strip">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announced}
      </div>
      <span className={styles.text}>{NEXT_STEP_STRIP_COPY[step]}</span>
      <button type="button" className={styles.showBtn} onClick={() => onShow(selector!)}>
        Show
      </button>
    </div>
  )
}
