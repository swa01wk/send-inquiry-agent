import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SignInPromptPayload } from '../../types/contracts'
import { SignInPromptCard } from './SignInPromptCard'

const payload: SignInPromptPayload = {
  message: 'This CR is already registered. Sign in to continue.',
  sign_in_url: '/tenant',
  button_label: 'Sign in',
}

describe('SignInPromptCard', () => {
  it('renders message and sign-in link', () => {
    render(<SignInPromptCard payload={payload} />)
    expect(screen.getByText(payload.message)).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /sign in/i })
    expect(link).toHaveAttribute('href', '/tenant')
  })
})
