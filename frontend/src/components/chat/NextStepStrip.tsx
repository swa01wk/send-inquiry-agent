import { useEffect, useRef, useState } from 'react'
import type { DraftSummary } from '../../types/contracts'
import type { ChatMessage } from '../../state/chatStore'
import type { UiCard } from '../../types/contracts'
import { NEXT_STEP_STRIP_COPY, nextStepStripStep, stageScrollTarget } from './inquiryProgress'
import { shouldShowNextStepStrip } from './nextStepStripVisibility'
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
  const stage =
    step === 'verify_email' || step === 'verify_mobile'
      ? 'contact'
      : step === 'documents'
        ? 'documents'
        : 'review'
  const target = stageScrollTarget(stage, draft, cards, messages)
  if (!target) return null
  if (target.kind === 'selector') return target.selector
  return `[data-testid="card-slot-${target.cardId}"]`
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
