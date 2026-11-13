import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { draftEmpty, draftMidway, verificationCardExample } from '../../mocks/fixtures'
import type { ChatMessage } from '../../state/chatStore'
import { ProgressStages } from './ProgressStages'

describe('ProgressStages', () => {
  it('marks gate phase with Company current', () => {
    render(<ProgressStages phase="gate" draft={draftEmpty} cards={{}} messages={[]} />)
    expect(screen.getByTestId('stage-company')).toHaveAttribute('data-state', 'current')
    expect(screen.getByTestId('stage-brand')).toHaveAttribute('data-state', 'upcoming')
  })

  it('marks submitted phase with all stages done', () => {
    render(<ProgressStages phase="submitted" draft={draftMidway} cards={{}} messages={[]} />)
    for (const key of ['company', 'brand', 'space', 'contact', 'documents', 'review']) {
      expect(screen.getByTestId(`stage-${key}`)).toHaveAttribute('data-state', 'done')
    }
  })

  it('derives collecting stage from next_step fields', () => {
    render(<ProgressStages phase="collecting" draft={draftMidway} cards={{}} messages={[]} />)
    expect(screen.getByTestId('stage-company')).toHaveAttribute('data-state', 'current')
  })

  it('scrolls when a tab with a shown card is clicked', () => {
    const card = verificationCardExample
    const messages: ChatMessage[] = [
      { id: 'a1', role: 'assistant', text: 'Verify', cardIds: [card.card_id] },
    ]
    const onStageClick = vi.fn()
    render(
      <ProgressStages
        phase="verifying"
        draft={{
          ...draftMidway,
          checks: {
            ...draftMidway.checks,
            next_step: 'verify_email',
            remaining: ['verify_email', 'terms'],
          },
        }}
        cards={{ [card.card_id]: card }}
        messages={messages}
        onStageClick={onStageClick}
      />,
    )
    fireEvent.click(screen.getByTestId('stage-contact'))
    expect(onStageClick).toHaveBeenCalledWith('contact')
  })

  it('disables tabs whose card has not been shown', () => {
    render(<ProgressStages phase="verifying" draft={draftMidway} cards={{}} messages={[]} />)
    expect(screen.getByTestId('stage-contact')).toHaveAttribute('aria-disabled', 'true')
  })

  it('uses flow v2 section tabs when sections are present', () => {
    render(
      <ProgressStages
        phase="collecting"
        draft={{
          ...draftEmpty,
          section: 'unit_and_category',
          checks: {
            ...draftEmpty.checks,
            sections: [
              { key: 'company_registration', label: 'Company Registration', done: true },
              { key: 'unit_and_category', label: 'Unit Type and Sales Category', done: false },
            ],
          },
        }}
        cards={{}}
        messages={[]}
      />,
    )
    expect(screen.getByTestId('stage-company_registration')).toHaveAttribute('data-state', 'done')
    expect(screen.getByTestId('stage-unit_and_category')).toHaveAttribute('data-state', 'current')
  })
})
