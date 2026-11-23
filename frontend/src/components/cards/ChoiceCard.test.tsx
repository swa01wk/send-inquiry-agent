import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { choiceCardExample } from '../../mocks/fixtures'
import type { ChoicePayload } from '../../types/contracts'
import { ChoiceCard } from './ChoiceCard'

function examplePayload(): ChoicePayload {
  if (choiceCardExample.card_type !== 'choice') throw new Error('bad fixture')
  return choiceCardExample.payload
}

describe('ChoiceCard (18 Nov B1)', () => {
  it('shows each option and sends the tapped one', async () => {
    const user = userEvent.setup()
    const onChoose = vi.fn()
    render(<ChoiceCard payload={examplePayload()} onChoose={onChoose} />)

    expect(screen.getByTestId('choice-card-sales_category')).toHaveAttribute('dir', 'ltr')
    expect(screen.getAllByRole('button')).toHaveLength(2)
    await user.click(screen.getByTestId('choice-option-fnb_cafe'))
    expect(onChoose).toHaveBeenCalledWith('fnb_cafe')
    // Picked: the others are disabled, so a second tap can't send another value.
    expect(screen.getByTestId('choice-option-fnb_restaurant')).toBeDisabled()
    expect(screen.getByTestId('choice-option-fnb_cafe')).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows the Arabic labels right to left', () => {
    render(<ChoiceCard payload={{ ...examplePayload(), lang: 'ar' }} onChoose={() => {}} />)

    const card = screen.getByTestId('choice-card-sales_category')
    expect(card).toHaveAttribute('dir', 'rtl')
    expect(screen.getByTestId('choice-option-fnb_cafe')).toHaveTextContent('أغذية ومشروبات · مقهى')
  })

  it('renders up to four options and the chosen state from the payload', () => {
    const payload = examplePayload()
    const options = [
      ...payload.options,
      { value: 'fashion', label: 'Retail · Fashion', label_ar: 'تجزئة · أزياء' },
      { value: 'electronics', label: 'Retail · Electronics', label_ar: null },
    ]
    render(<ChoiceCard payload={{ ...payload, options, chosen: 'fashion' }} onChoose={() => {}} />)

    expect(screen.getAllByRole('button')).toHaveLength(4)
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
    expect(screen.getByTestId('choice-option-fashion')).toHaveAttribute('aria-pressed', 'true')
  })
})
