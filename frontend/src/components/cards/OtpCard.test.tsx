import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { otpCardExample } from '../../mocks/fixtures'
import { OtpCard } from './OtpCard'

describe('OtpCard', () => {
  it('strips non-digits, caps at 4, and verifies', async () => {
    const user = userEvent.setup()
    const onVerify = vi.fn()
    if (otpCardExample.card_type !== 'otp_input') throw new Error('bad fixture')

    render(
      <OtpCard payload={otpCardExample.payload} onVerify={onVerify} onResend={() => undefined} />,
    )

    const input = screen.getByLabelText(/verification code/i)
    await user.type(input, '12ab34')
    expect(input).toHaveValue('1234')
    await user.click(screen.getByRole('button', { name: /verify/i }))
    expect(onVerify).toHaveBeenCalledWith('1234')
  })

  it('shows error caption with attempts left', () => {
    if (otpCardExample.card_type !== 'otp_input') throw new Error('bad fixture')
    render(
      <OtpCard
        payload={{ ...otpCardExample.payload, attempts_left: 2 }}
        onVerify={() => undefined}
        onResend={() => undefined}
      />,
    )
    expect(screen.getByText(/2 attempts left/i)).toBeInTheDocument()
  })
})
