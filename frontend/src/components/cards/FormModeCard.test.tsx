import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { FormModePayload } from '../../types/contracts'
import { FormModeCard } from './FormModeCard'

vi.mock('../../api/client', () => ({
  fetchMasterKind: vi.fn(async () => [
    { id: 'store', label: 'Store', code: 'STR' },
    { id: 'specialty', label: 'Specialty', code: 'SPC' },
  ]),
}))

function renderCard(payload: FormModePayload) {
  const handlers = {
    onCheckCr: vi.fn(),
    onSkipCr: vi.fn(),
    onSaveField: vi.fn(async () => true),
    onCallMe: vi.fn(),
  }
  render(<FormModeCard payload={payload} {...handlers} />)
  return handlers
}

const base: FormModePayload = {
  active: true,
  message: "Start with your company's CR number, or skip it for now.",
  next_step: 'cr',
  fields: [],
  can_skip_cr: true,
}

describe('FormModeCard', () => {
  it('checks or skips the CR', async () => {
    const user = userEvent.setup()
    const handlers = renderCard(base)
    expect(screen.getByText(/finish your inquiry here/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /check cr/i })).toBeDisabled()
    await user.type(screen.getByLabelText('CR number'), '1010123456')
    await user.click(screen.getByRole('button', { name: /check cr/i }))
    expect(handlers.onCheckCr).toHaveBeenCalledWith('1010123456')
    await user.click(screen.getByRole('button', { name: /skip for now/i }))
    expect(handlers.onSkipCr).toHaveBeenCalled()
  })

  it('saves a missing text field and a select field', async () => {
    const user = userEvent.setup()
    const handlers = renderCard({
      ...base,
      next_step: 'details',
      can_skip_cr: false,
      fields: [
        { key: 'brand_name_en', label: 'Brand name (EN)', kind: 'text', master_kind: null },
        { key: 'unit_type', label: 'Unit type', kind: 'select', master_kind: 'unit_types' },
      ],
    })
    expect(screen.queryByLabelText('CR number')).not.toBeInTheDocument()

    await user.type(screen.getByLabelText('Brand name (EN)'), 'Bean Street')
    const brandRow = screen.getByTestId('form-mode-field-brand_name_en')
    await user.click(brandRow.querySelector('button') as HTMLButtonElement)
    expect(handlers.onSaveField).toHaveBeenCalledWith('brand_name_en', 'Bean Street')

    await screen.findByRole('option', { name: 'Specialty' })
    await user.selectOptions(screen.getByLabelText('Unit type'), 'specialty')
    const unitRow = screen.getByTestId('form-mode-field-unit_type')
    await user.click(unitRow.querySelector('button') as HTMLButtonElement)
    expect(handlers.onSaveField).toHaveBeenCalledWith('unit_type', 'specialty')
  })

  it('shows an error when a value is refused', async () => {
    const user = userEvent.setup()
    const onSaveField = vi.fn(async () => false)
    render(
      <FormModeCard
        payload={{
          ...base,
          next_step: 'details',
          fields: [{ key: 'email', label: 'Email', kind: 'text', master_kind: null }],
        }}
        onCheckCr={vi.fn()}
        onSkipCr={vi.fn()}
        onSaveField={onSaveField}
        onCallMe={vi.fn()}
      />,
    )
    await user.type(screen.getByLabelText('Email'), 'not-an-email{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent(/doesn't look right/i)
  })

  it('offers a call back', async () => {
    const user = userEvent.setup()
    const handlers = renderCard({ ...base, next_step: 'verification', can_skip_cr: false })
    await user.click(screen.getByRole('button', { name: /ask us to call you/i }))
    expect(handlers.onCallMe).toHaveBeenCalled()
  })

  it('says when the assistant is back, with no actions', () => {
    renderCard({ ...base, active: false, message: 'Our assistant is back.' })
    expect(screen.getByText('Our assistant is back.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
