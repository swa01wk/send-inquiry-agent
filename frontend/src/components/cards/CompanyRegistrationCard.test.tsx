import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CompanyRegistrationPayload } from '../../types/contracts'
import { CompanyRegistrationCard } from './CompanyRegistrationCard'

const basePayload: CompanyRegistrationPayload = {
  prompt: 'Enter your CR number to check registration, or skip.',
  input_placeholder: '10-digit CR number',
  verify_label: 'Verify',
  skip_label: 'Skip',
  skip_confirm: {
    prompt: 'Are you sure you want to proceed without CR ID?',
    yes_label: 'Yes, continue without it',
    no_label: "No, I'll enter it",
  },
  state: 'open',
  cr_masked: null,
  error: null,
}

describe('CompanyRegistrationCard', () => {
  it('verifies a CR from the input', async () => {
    const user = userEvent.setup()
    const onVerify = vi.fn()
    render(
      <CompanyRegistrationCard
        payload={basePayload}
        onVerify={onVerify}
        onSkip={() => undefined}
        onConfirmSkip={() => undefined}
        onDismissSkipConfirm={() => undefined}
      />,
    )
    await user.type(screen.getByPlaceholderText('10-digit CR number'), '1010123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(onVerify).toHaveBeenCalledWith('1010123456')
  })

  it('shows skip confirm and confirms', async () => {
    const user = userEvent.setup()
    const onConfirmSkip = vi.fn()
    render(
      <CompanyRegistrationCard
        payload={{ ...basePayload, state: 'confirm_skip' }}
        onVerify={() => undefined}
        onSkip={() => undefined}
        onConfirmSkip={onConfirmSkip}
        onDismissSkipConfirm={() => undefined}
      />,
    )
    await user.click(screen.getByRole('button', { name: /yes, continue without it/i }))
    expect(onConfirmSkip).toHaveBeenCalled()
  })
})
