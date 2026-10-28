import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HandoffCard } from './HandoffCard'

describe('HandoffCard', () => {
  it('shows contact links, hours, reference and case id when set', () => {
    render(
      <HandoffCard
        payload={{
          phone: '+966 11 000 0000',
          email: 'leasing-callcentre@example.com',
          hours: 'Sunday to Thursday, 9 am to 5 pm (Riyadh time)',
          short_ref: 'GEO-STR-123456',
          case_id: 'CC-000042',
          reason: 'user_asked',
        }}
      />,
    )

    expect(screen.getByRole('link', { name: '+966 11 000 0000' })).toHaveAttribute(
      'href',
      'tel:+966110000000',
    )
    expect(screen.getByRole('link', { name: 'leasing-callcentre@example.com' })).toHaveAttribute(
      'href',
      'mailto:leasing-callcentre@example.com',
    )
    expect(screen.getByText(/Sunday to Thursday/)).toBeInTheDocument()
    expect(screen.getByText(/Your reference: GEO-STR-123456/)).toBeInTheDocument()
    expect(screen.getByText(/Case CC-000042/)).toBeInTheDocument()
  })

  it('omits case id when empty', () => {
    render(
      <HandoffCard
        payload={{
          phone: '+966 11 000 0000',
          email: 'leasing-callcentre@example.com',
          hours: 'Sunday to Thursday, 9 am to 5 pm (Riyadh time)',
          short_ref: 'INQ-ABCDEF',
          case_id: '',
          reason: 'user_asked',
        }}
      />,
    )
    expect(screen.queryByText(/Case /)).not.toBeInTheDocument()
  })
})
