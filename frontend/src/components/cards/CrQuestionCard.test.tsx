import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CrQuestionPayload } from '../../types/contracts'
import { CrQuestionCard } from './CrQuestionCard'

const basePayload: CrQuestionPayload = {
  prompt: 'Does your company have a CR?',
  yes_label: 'Yes, we have a CR',
  no_label: "No, we don't",
  answered: null,
}

describe('CrQuestionCard', () => {
  it('fires cr_answer with has_cr true', async () => {
    const user = userEvent.setup()
    const onAnswer = vi.fn()
    render(<CrQuestionCard payload={basePayload} onAnswer={onAnswer} />)
    await user.click(screen.getByRole('button', { name: /yes, we have a cr/i }))
    expect(onAnswer).toHaveBeenCalledWith(true)
  })

  it('fires cr_answer with has_cr false', async () => {
    const user = userEvent.setup()
    const onAnswer = vi.fn()
    render(<CrQuestionCard payload={basePayload} onAnswer={onAnswer} />)
    await user.click(screen.getByRole('button', { name: /no, we don't/i }))
    expect(onAnswer).toHaveBeenCalledWith(false)
  })

  it('shows the chosen label when answered', () => {
    render(
      <CrQuestionCard payload={{ ...basePayload, answered: 'yes' }} onAnswer={() => undefined} />,
    )
    expect(screen.getByText('Yes, we have a CR')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
