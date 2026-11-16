import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
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

  it('M2: offers "I don\'t have a login" and sends it', async () => {
    const user = userEvent.setup()
    const onNoLogin = vi.fn()
    render(
      <SignInPromptCard
        payload={{ ...payload, no_login_label: "I don't have a login" }}
        onNoLogin={onNoLogin}
      />,
    )
    await user.click(screen.getByRole('button', { name: "I don't have a login" }))
    expect(onNoLogin).toHaveBeenCalledTimes(1)
  })

  it('M2: without the policy there is no second button', () => {
    render(<SignInPromptCard payload={payload} onNoLogin={() => undefined} />)
    expect(screen.queryByRole('button', { name: "I don't have a login" })).not.toBeInTheDocument()
  })

  it('M2: once they continue, the buttons give way to a line', () => {
    render(<SignInPromptCard payload={{ ...payload, continued_without_login: true }} />)
    expect(screen.getByTestId('continued-without-login')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /sign in/i })).not.toBeInTheDocument()
  })
})
