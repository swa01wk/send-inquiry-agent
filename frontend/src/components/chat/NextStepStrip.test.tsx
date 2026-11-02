import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { verificationCardExample } from '../../mocks/fixtures'
import type { ChatMessage } from '../../state/chatStore'
import { NextStepStrip, shouldShowNextStepStrip } from './NextStepStrip'

describe('NextStepStrip', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        private readonly callback: IntersectionObserverCallback
        constructor(callback: IntersectionObserverCallback) {
          this.callback = callback
        }
        observe() {
          this.callback(
            [{ isIntersecting: false } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver,
          )
        }
        disconnect() {}
        unobserve() {}
        takeRecords() {
          return []
        }
        get root() {
          return null
        }
        get rootMargin() {
          return ''
        }
        get thresholds() {
          return []
        }
      },
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows only for post-collection steps', () => {
    expect(
      shouldShowNextStepStrip({
        draft: {
          phase: 'gate',
          fields: [],
          documents: [],
          checks: {
            required_filled: 0,
            required_total: 11,
            unconfirmed: 0,
            email_verified: false,
            mobile_verified: false,
            contact_verified: false,
            required_docs_uploaded: 0,
            required_docs_total: 2,
            terms_accepted: false,
            remaining: ['cr'],
            next_step: 'cr',
          },
          can_submit: false,
          changed_keys: [],
          follow_on_of: null,
        },
        phase: 'gate',
      }),
    ).toBe(false)
  })

  it('hides in assisted and form mode', () => {
    const draft = {
      phase: 'verifying' as const,
      fields: [],
      documents: [],
      checks: {
        required_filled: 10,
        required_total: 11,
        unconfirmed: 0,
        email_verified: false,
        mobile_verified: false,
        contact_verified: false,
        required_docs_uploaded: 0,
        required_docs_total: 2,
        terms_accepted: false,
        remaining: ['verify_email' as const],
        next_step: 'verify_email' as const,
      },
      can_submit: false,
      changed_keys: [],
      follow_on_of: null,
    }
    expect(shouldShowNextStepStrip({ draft, phase: 'verifying', assistedIntake: true })).toBe(false)
    expect(shouldShowNextStepStrip({ draft, phase: 'verifying', formModeActive: true })).toBe(false)
  })

  it('renders verify_email copy when the card is out of view', async () => {
    const card = verificationCardExample
    const messages: ChatMessage[] = [
      { id: 'a1', role: 'assistant', text: 'Verify', cardIds: [card.card_id] },
    ]
    render(
      <NextStepStrip
        draft={{
          phase: 'verifying',
          fields: [],
          documents: [],
          checks: {
            required_filled: 10,
            required_total: 11,
            unconfirmed: 0,
            email_verified: false,
            mobile_verified: false,
            contact_verified: false,
            required_docs_uploaded: 0,
            required_docs_total: 2,
            terms_accepted: false,
            remaining: ['verify_email'],
            next_step: 'verify_email',
          },
          can_submit: false,
          changed_keys: [],
          follow_on_of: null,
        }}
        phase="verifying"
        cards={{ [card.card_id]: card }}
        messages={messages}
        onShow={() => {}}
      />,
    )
    expect(await screen.findByTestId('next-step-strip')).toHaveTextContent(
      'Next: open the link we emailed you',
    )
  })
})
