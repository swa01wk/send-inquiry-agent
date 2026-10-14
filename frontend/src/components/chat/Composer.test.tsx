import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Composer } from './Composer'

describe('Composer', () => {
  it('sends on Enter', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<Composer disabled={false} onSend={onSend} />)

    const input = screen.getByRole('textbox')
    await user.type(input, 'Hello{Enter}')

    expect(onSend).toHaveBeenCalledWith('Hello')
  })

  it('is disabled while streaming', () => {
    render(<Composer disabled onSend={() => undefined} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled()
  })
})
