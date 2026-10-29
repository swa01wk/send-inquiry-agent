import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ExistingCrChoicePayload } from '../../types/contracts'
import { ExistingCrChoiceCard } from './ExistingCrChoiceCard'

const basePayload: ExistingCrChoicePayload = {
  cr_number: '1010000000',
  company_name: 'Oasis Coffee Company',
  options: [
    { value: 'sign_in', label: 'Sign in to Tenant Central' },
    { value: 'continue', label: 'Continue as a new inquiry' },
  ],
}

describe('ExistingCrChoiceCard', () => {
  it('shows headline and fires choice action', async () => {
    const user = userEvent.setup()
    const onChoose = vi.fn()
    render(<ExistingCrChoiceCard payload={basePayload} onChoose={onChoose} />)
    expect(
      screen.getByText('Oasis Coffee Company (CR 1010000000) already has a Tenant Central account'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sign in to tenant central/i }))
    expect(onChoose).toHaveBeenCalledWith('sign_in')
  })

  it('shows done label when chosen', () => {
    render(
      <ExistingCrChoiceCard
        payload={{ ...basePayload, chosen: 'continue' }}
        onChoose={() => undefined}
      />,
    )
    expect(screen.getByText('Continue as a new inquiry')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
