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
})
