import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { verificationCardExample } from '../../mocks/fixtures'
import type { VerificationPayload } from '../../types/contracts'
import { VerificationCard } from './VerificationCard'

function examplePayload(): VerificationPayload {
  if (verificationCardExample.card_type !== 'verification') throw new Error('bad fixture')
  return verificationCardExample.payload
}

const noop = () => undefined

describe('VerificationCard', () => {
  it('strips non-digits, caps at 4, and verifies the SMS code', async () => {
    const user = userEvent.setup()
    const onVerifyCode = vi.fn()
    render(
      <VerificationCard
        payload={examplePayload()}
        onVerifyEmail={noop}
        onResendEmailLink={noop}
        onVerifyCode={onVerifyCode}
        onResendCode={noop}
      />,
    )

    const input = screen.getByLabelText(/verification code/i)
    await user.type(input, '12ab34')
    expect(input).toHaveValue('1234')
    await user.click(screen.getByRole('button', { name: /^verify$/i }))
    expect(onVerifyCode).toHaveBeenCalledWith('1234')
  })

  it('opens the demo email link with its token', async () => {
    const user = userEvent.setup()
    const onVerifyEmail = vi.fn()
    render(
      <VerificationCard
        payload={examplePayload()}
        onVerifyEmail={onVerifyEmail}
        onResendEmailLink={noop}
        onVerifyCode={noop}
        onResendCode={noop}
      />,
    )
    await user.click(screen.getByRole('button', { name: /open verification link/i }))
    expect(onVerifyEmail).toHaveBeenCalledWith('demo-token')
  })

  it('shows error caption with attempts left', () => {
    const payload = examplePayload()
    render(
      <VerificationCard
        payload={{ ...payload, mobile: payload.mobile && { ...payload.mobile, attempts_left: 2 } }}
        onVerifyEmail={noop}
        onResendEmailLink={noop}
        onVerifyCode={noop}
        onResendCode={noop}
      />,
    )
    expect(screen.getByText(/2 attempts left/i)).toBeInTheDocument()
  })

  it('shows only the email section for a landline-only applicant', () => {
    render(
      <VerificationCard
        payload={{ ...examplePayload(), mobile: null }}
        onVerifyEmail={noop}
        onResendEmailLink={noop}
        onVerifyCode={noop}
        onResendCode={noop}
      />,
    )
    expect(screen.queryByLabelText(/verification code/i)).not.toBeInTheDocument()
    expect(screen.getByText(/we sent a verification link/i)).toBeInTheDocument()
  })
})
