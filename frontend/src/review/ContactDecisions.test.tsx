import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { BriefContact } from '../api/review'
import { ContactDecisions } from './ContactDecisions'

const BILLING: BriefContact = {
  role: 'billing_contact',
  label: 'Billing Contact',
  name: 'Omar Saleh',
  email: 'omar@beanstreet.example',
  phone: '+966551234567',
  same_as_primary: false,
  contact_id: 'ct_1',
}

describe('ContactDecisions', () => {
  it('shows no approval chip or buttons when per-contact approval is off (flow v2, V7)', () => {
    render(
      <ContactDecisions
        contacts={[{ ...BILLING, approval: null }]}
        canDecide
        busy={false}
        onAct={vi.fn()}
      />,
    )
    expect(screen.getByTestId('contact-row-billing_contact')).toHaveTextContent('Omar Saleh')
    expect(screen.queryByTestId('contact-approval-billing_contact')).not.toBeInTheDocument()
    expect(screen.queryByText('Waiting for approval')).not.toBeInTheDocument()
    expect(screen.queryByTestId('contact-approve-billing_contact')).not.toBeInTheDocument()
  })

  it('still shows the chip when approval is on', () => {
    render(
      <ContactDecisions
        contacts={[{ ...BILLING, approval: 'pending' }]}
        canDecide={false}
        busy={false}
        onAct={vi.fn()}
      />,
    )
    expect(screen.getByTestId('contact-approval-billing_contact')).toHaveTextContent(
      'Waiting for approval',
    )
  })
})
