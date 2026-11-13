import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ContactCheckPayload, InformTenantPayload } from '../../types/contracts'
import { ContactCheckCard } from './ContactCheckCard'
import { InformTenantCard } from './InformTenantCard'

const open: ContactCheckPayload = {
  prompt:
    "This CR already has a Tenant Central account (Oasis Coffee Company). Ask for the caller's email to check whether they already have a login.",
  company_name: 'Oasis Coffee Company',
  input_placeholder: "Caller's email",
  check_label: 'Check contact',
  state: 'open',
  email_masked: null,
  error: null,
}

const inform: InformTenantPayload = {
  title: 'Inform the caller to raise the inquiry on Tenant Central',
  say: 'You already have a Tenant Central account. Please sign in and raise the inquiry from Leasing Opportunities.',
  email_masked: 'l***@oasiscoffee.example',
  sign_in_label: 'Email sign-in link',
  offer_sign_in_link: true,
  sent: false,
  error: null,
}

describe('ContactCheckCard', () => {
  it('sends the trimmed email on Check contact', () => {
    const onCheck = vi.fn()
    render(<ContactCheckCard payload={open} onCheck={onCheck} />)
    const button = screen.getByRole('button', { name: 'Check contact' })
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Caller's email"), {
      target: { value: '  layla@oasiscoffee.example ' },
    })
    fireEvent.click(button)
    expect(onCheck).toHaveBeenCalledWith('layla@oasiscoffee.example')
  })

  it('shows the error and keeps the input open', () => {
    render(
      <ContactCheckCard
        payload={{ ...open, error: 'Please enter a valid email.' }}
        onCheck={vi.fn()}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Please enter a valid email.')
    expect(screen.getByLabelText("Caller's email")).toBeInTheDocument()
  })

  it('locks once checked', () => {
    render(
      <ContactCheckCard
        payload={{ ...open, state: 'existing', email_masked: 'l***@oasiscoffee.example' }}
        onCheck={vi.fn()}
      />,
    )
    expect(screen.getByText(/already has a Tenant Central login/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says a new contact is captured fresh', () => {
    render(
      <ContactCheckCard
        payload={{ ...open, state: 'new', email_masked: 'h***@oasiscoffee.example' }}
        onCheck={vi.fn()}
      />,
    )
    expect(screen.getByText(/new contact/)).toBeInTheDocument()
  })
})

describe('InformTenantCard', () => {
  it('shows the words to say and emails the sign-in link', () => {
    const onSend = vi.fn()
    render(<InformTenantCard payload={inform} onSendSignInLink={onSend} />)
    expect(screen.getByTestId('inform-tenant-say')).toHaveTextContent(/sign in and raise/)
    fireEvent.click(screen.getByRole('button', { name: 'Email sign-in link' }))
    expect(onSend).toHaveBeenCalledOnce()
  })

  it('shows only the words to say when the sign-in link is off', () => {
    render(
      <InformTenantCard
        payload={{ ...inform, offer_sign_in_link: false }}
        onSendSignInLink={vi.fn()}
      />,
    )
    expect(screen.getByTestId('inform-tenant-say')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('shows the sent state without a button', () => {
    render(<InformTenantCard payload={{ ...inform, sent: true }} onSendSignInLink={vi.fn()} />)
    expect(screen.getByText('Sign-in link sent to l***@oasiscoffee.example')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
