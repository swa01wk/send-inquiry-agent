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

  it('M1: uploads the CR certificate instead of typing', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockResolvedValue(undefined)
    render(
      <CompanyRegistrationCard
        payload={{ ...basePayload, allowed_extensions: ['.pdf'] }}
        onVerify={() => undefined}
        onSkip={() => undefined}
        onConfirmSkip={() => undefined}
        onDismissSkipConfirm={() => undefined}
        onUploadCertificate={onUpload}
      />,
    )
    expect(screen.getByRole('button', { name: 'Upload CR certificate' })).toBeInTheDocument()
    const file = new File(['%PDF'], 'cr_certificate_new.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByTestId('cr-certificate-input'), file)
    expect(onUpload).toHaveBeenCalledWith(file)
  })

  it('M1: refuses a file type the server would refuse, without uploading', async () => {
    const onUpload = vi.fn()
    render(
      <CompanyRegistrationCard
        payload={{ ...basePayload, allowed_extensions: ['.pdf'] }}
        onVerify={() => undefined}
        onSkip={() => undefined}
        onConfirmSkip={() => undefined}
        onDismissSkipConfirm={() => undefined}
        onUploadCertificate={onUpload}
      />,
    )
    const input = screen.getByTestId('cr-certificate-input') as HTMLInputElement
    const file = new File(['x'], 'notes.txt', { type: 'text/plain' })
    const user = userEvent.setup({ applyAccept: false })
    await user.upload(input, file)
    expect(onUpload).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent("That file type isn't supported.")
  })

  it('M1: shows the certificate name once uploaded', () => {
    render(
      <CompanyRegistrationCard
        payload={{ ...basePayload, certificate_name: 'cr_certificate_new.pdf' }}
        onVerify={() => undefined}
        onSkip={() => undefined}
        onConfirmSkip={() => undefined}
        onDismissSkipConfirm={() => undefined}
      />,
    )
    expect(screen.getByTestId('cr-certificate-name')).toHaveTextContent(
      'CR certificate: cr_certificate_new.pdf',
    )
  })

  it('M2: locks the card once they continue without a login', () => {
    render(
      <CompanyRegistrationCard
        payload={{ ...basePayload, state: 'continued_no_login', cr_masked: '••••••0000' }}
        onVerify={() => undefined}
        onSkip={() => undefined}
        onConfirmSkip={() => undefined}
        onDismissSkipConfirm={() => undefined}
      />,
    )
    expect(screen.getByText(/continuing as a new inquiry without a login/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument()
  })
})
