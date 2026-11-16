import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DuplicateNoticeCard } from './DuplicateNoticeCard'

describe('DuplicateNoticeCard', () => {
  it('shows the notice as a note, with the policy on the card', () => {
    render(
      <DuplicateNoticeCard
        payload={{
          reference: 'GEO-STR-000201',
          malls: ['Riyadh Mall A'],
          policy: 'warn',
          message:
            "There's already an open inquiry for this CR at Riyadh Mall A (GEO-STR-000201). You can still send this one; the leasing team will see both.",
        }}
      />,
    )
    const note = screen.getByRole('note')
    expect(note).toHaveAttribute('data-policy', 'warn')
    expect(note).toHaveTextContent('GEO-STR-000201')
    expect(note).toHaveTextContent('You can still send this one')
  })
})
