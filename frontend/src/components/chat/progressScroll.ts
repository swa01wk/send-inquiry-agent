import type { ChatMessage } from '../../state/chatStore'
import type { DraftSummary, UiCard } from '../../types/contracts'
import { stageScrollTarget, type ProgressStageKey } from './inquiryProgress'

export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function scrollToProgressStage(
  stage: ProgressStageKey,
  draft: DraftSummary,
  cards: Record<string, UiCard>,
  messages: ChatMessage[],
): boolean {
  const target = stageScrollTarget(stage, draft, cards, messages)
  if (!target) return false

  let el: Element | null = null
  if (target.kind === 'selector') {
    el = document.querySelector(target.selector)
  } else {
    el = document.querySelector(`[data-testid="confirm-fields-${target.cardId}"]`)
  }
  if (!el || !(el instanceof HTMLElement)) return false

  el.scrollIntoView({
    block: 'center',
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
  })
  return true
}

export function scrollToSelector(selector: string): boolean {
  const el = document.querySelector(selector)
  if (!el || !(el instanceof HTMLElement)) return false
  el.scrollIntoView({
    block: 'center',
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
  })
  return true
}
