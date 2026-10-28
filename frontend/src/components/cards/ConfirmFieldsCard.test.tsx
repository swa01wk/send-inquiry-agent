import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { confirmFieldsCardExample } from '../../mocks/fixtures'
import { ConfirmFieldsCard } from './ConfirmFieldsCard'

describe('ConfirmFieldsCard', () => {
  it('renders fixture fields and calls confirm', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')

    render(
      <ConfirmFieldsCard
        cardId={confirmFieldsCardExample.card_id}
        payload={confirmFieldsCardExample.payload}
        onConfirm={onConfirm}
      />,
    )

    expect(screen.getByText('CR number')).toBeInTheDocument()
    expect(screen.getByText('1010123456')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /looks right/i }))
    expect(onConfirm).toHaveBeenCalled()
  })

  it('shows evidence under derived values when set', () => {
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')
    render(
      <ConfirmFieldsCard
        cardId="confirm-evidence"
        payload={{
          ...confirmFieldsCardExample.payload,
          fields: [
            {
              key: 'unit_type',
              label: 'Unit type',
              display: 'Specialty',
              source: 'derived',
              confirmed: false,
              evidence: 'specialty coffee kiosk',
            },
          ],
          all_confirmed: false,
        }}
        onConfirm={() => {}}
      />,
    )
    expect(screen.getByText("from: 'specialty coffee kiosk'")).toBeInTheDocument()
  })
})
