import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ContactsPayload } from '../../types/contracts'
import { ContactsCard } from './ContactsCard'

const sample: ContactsPayload = {
  request_id: 'req-contacts',
  remarks: 'We need billing and signatory details.',
  rows: [
    {
      role: 'authorized_signatory',
      label: 'Authorized signatory',
      required: true,
      first_name: 'Sara',
      last_name: 'Al-Harbi',
      email: 'sara@example.com',
      phone: '+966501234567',
      source: 'user',
      confirmed: true,
      same_as_primary: false,
    },
    {
      role: 'billing_contact',
      label: 'Billing contact',
      required: true,
      first_name: null,
      last_name: null,
      email: null,
      phone: null,
      source: null,
      confirmed: false,
      same_as_primary: false,
    },
  ],
  can_submit: false,
  blockers: ['missing_contact:billing_contact'],
}

describe('ContactsCard', () => {
  it('renders rows, blocker text, and disables send when blocked', async () => {
    const onSubmit = vi.fn()
    render(<ContactsCard payload={sample} onSubmit={onSubmit} />)

    expect(screen.getByText('Sara Al-Harbi · sara@example.com · +966501234567')).toBeInTheDocument()
    expect(screen.getByText('Billing contact is missing')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send contacts/i })).toBeDisabled()
  })

  it('sends submit_contacts when can_submit', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <ContactsCard
        payload={{
          ...sample,
          can_submit: true,
          blockers: [],
          rows: sample.rows.map((r) =>
            r.role === 'billing_contact'
              ? {
                  ...r,
                  first_name: 'Omar',
                  last_name: 'Saleh',
                  email: 'omar@example.com',
                  phone: '+966509876543',
                  source: 'user',
                  confirmed: true,
                }
              : r,
          ),
        }}
        onSubmit={onSubmit}
      />,
    )

    await user.click(screen.getByRole('button', { name: /send contacts/i }))
    expect(onSubmit).toHaveBeenCalled()
  })
})
