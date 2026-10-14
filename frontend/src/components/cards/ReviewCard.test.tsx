import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { reviewCardExample } from '../../mocks/fixtures'
import { ReviewCard } from './ReviewCard'

describe('ReviewCard', () => {
  it('keeps submit disabled until consent and saves edit', async () => {
    const user = userEvent.setup()
    const onEditField = vi.fn(async () => true)
    const onSubmit = vi.fn()
    if (reviewCardExample.card_type !== 'review') throw new Error('bad fixture')

    render(
      <ReviewCard
        payload={reviewCardExample.payload}
        onEditField={onEditField}
        onSubmit={onSubmit}
      />,
    )

    const submit = screen.getByRole('button', { name: /submit inquiry/i })
    expect(submit).toBeDisabled()

    await user.click(screen.getByRole('checkbox'))
    expect(submit).toBeEnabled()
    await user.click(submit)
    expect(onSubmit).toHaveBeenCalled()

    await user.click(screen.getAllByRole('button', { name: /^edit$/i })[0])
    const input = screen.getByRole('textbox')
    await user.clear(input)
    await user.type(input, 'New value')
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(onEditField).toHaveBeenCalledWith(expect.any(String), 'New value')
  })
})
