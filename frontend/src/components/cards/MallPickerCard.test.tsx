import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mallPickerCardExample } from '../../mocks/fixtures'
import { MallPickerCard } from './MallPickerCard'

describe('MallPickerCard', () => {
  it('disables Done with no selection and toggles aria-pressed', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    if (mallPickerCardExample.card_type !== 'mall_picker') throw new Error('bad fixture')

    const payload = { ...mallPickerCardExample.payload, selected: [] }
    render(<MallPickerCard payload={payload} locked={false} onDone={onDone} />)

    const done = screen.getByRole('button', { name: /done/i })
    expect(done).toBeDisabled()

    const tile = screen.getByRole('button', { name: /Riyadh Mall C/i })
    expect(tile).toHaveAttribute('aria-pressed', 'false')
    await user.click(tile)
    expect(tile).toHaveAttribute('aria-pressed', 'true')
    expect(done).toBeEnabled()
    await user.click(done)
    expect(onDone).toHaveBeenCalledWith(['riyadh-mall-c'])
  })

  it('keeps a single selection when max_select is 1', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    if (mallPickerCardExample.card_type !== 'mall_picker') throw new Error('bad fixture')

    const payload = { ...mallPickerCardExample.payload, selected: [], max_select: 1 }
    render(<MallPickerCard payload={payload} locked={false} onDone={onDone} />)

    await user.click(screen.getByRole('button', { name: /Riyadh Mall A/i }))
    await user.click(screen.getByRole('button', { name: /Riyadh Mall B/i }))
    expect(screen.getByRole('button', { name: /Riyadh Mall A/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    await user.click(screen.getByRole('button', { name: /done/i }))
    expect(onDone).toHaveBeenCalledWith(['riyadh-mall-b'])
  })
})
