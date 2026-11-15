import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { BriefContact } from '../api/review'
import { ContactList } from './ContactList'

const BILLING: BriefContact = {
  role: 'billing_contact',
  label: 'Billing Contact',
  name: 'Omar Saleh',
  email: 'omar@beanstreet.example',
  phone: '+966551234567',
  same_as_primary: false,
  contact_id: 'ct_1',
}

describe('ContactList', () => {
  it('lists each contact with no approval chip or buttons (flow v2, V7)', () => {
    render(<ContactList contacts={[BILLING]} />)
    expect(screen.getByTestId('contact-row-billing_contact')).toHaveTextContent(
      'Billing Contact: Omar Saleh, omar@beanstreet.example, +966551234567',
    )
    expect(screen.queryByText('Waiting for approval')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
