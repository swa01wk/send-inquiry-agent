import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { TermsCard } from './TermsCard'

const basePayload = {
  text: 'Please accept the terms before we continue.',
  privacy_url: '/privacy',
  accepted: false,
}

describe('TermsCard', () => {
  it('shows terms accepted immediately when the checkbox is ticked (optimistic)', async () => {
    const user = userEvent.setup()
    let resolve!: (value: boolean) => void
    const pending = new Promise<boolean>((resolveFn) => {
      resolve = resolveFn
    })
    const onAccept = vi.fn(() => pending)
    render(<TermsCard payload={basePayload} onAccept={onAccept} />)

    await user.click(screen.getByRole('checkbox'))

    expect(onAccept).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('terms-accepted')).toBeVisible()
    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('checkbox')).toBeDisabled()

    resolve(true)
    await waitFor(() => expect(screen.getByTestId('terms-accepted')).toBeVisible())
  })

  it('reverts and shows an error when accept fails', async () => {
    const user = userEvent.setup()
    const onAccept = vi.fn(async () => false)
    render(<TermsCard payload={basePayload} onAccept={onAccept} />)

    await user.click(screen.getByRole('checkbox'))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/couldn't save/i)
    })
    expect(screen.getByRole('checkbox')).not.toBeChecked()
  })

  it('shows accepted state from the payload', () => {
    render(<TermsCard payload={{ ...basePayload, accepted: true }} onAccept={() => undefined} />)
    expect(screen.getByTestId('terms-accepted')).toHaveTextContent(/terms accepted/i)
    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('checkbox')).toBeDisabled()
  })
})
