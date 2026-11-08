import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { SignatoryQuestionPayload } from '../../types/contracts'
import { SignatoryQuestionCard } from './SignatoryQuestionCard'

const basePayload: SignatoryQuestionPayload = {
  prompt: 'Are you the authorised signatory for your company?',
  yes_label: "Yes, I'm the authorised signatory",
  no_label: 'No, someone else is',
  answered: null,
}

describe('SignatoryQuestionCard', () => {
  it('fires signatory_answer with is_signatory true', async () => {
    const user = userEvent.setup()
    const onAnswer = vi.fn()
    render(<SignatoryQuestionCard payload={basePayload} onAnswer={onAnswer} />)
    await user.click(screen.getByRole('button', { name: /yes, i'm the authorised signatory/i }))
    expect(onAnswer).toHaveBeenCalledWith(true)
  })

  it('fires signatory_answer with is_signatory false', async () => {
    const user = userEvent.setup()
    const onAnswer = vi.fn()
    render(<SignatoryQuestionCard payload={basePayload} onAnswer={onAnswer} />)
    await user.click(screen.getByRole('button', { name: /no, someone else is/i }))
    expect(onAnswer).toHaveBeenCalledWith(false)
  })

  it('shows the chosen label when answered', () => {
    render(
      <SignatoryQuestionCard
        payload={{ ...basePayload, answered: 'yes' }}
        onAnswer={() => undefined}
      />,
    )
    expect(screen.getByText("Yes, I'm the authorised signatory")).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
