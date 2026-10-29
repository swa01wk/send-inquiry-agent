import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SendLinkPayload } from '../../types/contracts'
import { SendLinkCard } from './SendLinkCard'

const basePayload: SendLinkPayload = {
  email_masked: 'a***@example.com',
  can_send: false,
  missing: ['CR number'],
}

describe('SendLinkCard', () => {
  it('shows email and disables send when cannot send', () => {
    render(<SendLinkCard payload={basePayload} onSendLink={() => undefined} />)
    expect(screen.getByText(/Applicant email: a\*\*\*@example.com/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send application link/i })).toBeDisabled()
  })

  it('calls send when enabled', async () => {
    const user = userEvent.setup()
    const onSendLink = vi.fn()
    render(
      <SendLinkCard
        payload={{ ...basePayload, missing: [], can_send: true }}
        onSendLink={onSendLink}
      />,
    )
    await user.click(screen.getByRole('button', { name: /send application link/i }))
    expect(onSendLink).toHaveBeenCalled()
  })

  it('shows sent state and resend label', async () => {
    const user = userEvent.setup()
    const onSendLink = vi.fn()
    render(
      <SendLinkCard
        payload={{
          ...basePayload,
          missing: [],
          can_send: true,
          sent_to_masked: 'a***@example.com',
        }}
        onSendLink={onSendLink}
      />,
    )
    expect(screen.getByText(/Link sent to a\*\*\*@example.com/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /resend link/i }))
    expect(onSendLink).toHaveBeenCalled()
  })
})
