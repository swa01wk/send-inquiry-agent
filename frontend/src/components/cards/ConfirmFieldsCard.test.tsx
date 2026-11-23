import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { confirmFieldsCardExample } from '../../mocks/fixtures'
import { ConfirmFieldsCard } from './ConfirmFieldsCard'

describe('ConfirmFieldsCard', () => {
  it('confirms one row with its value button (18 Nov B1, M27)', async () => {
    const user = userEvent.setup()
    const onConfirmField = vi.fn()
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')

    render(
      <ConfirmFieldsCard
        cardId={confirmFieldsCardExample.card_id}
        payload={confirmFieldsCardExample.payload}
        onConfirmField={onConfirmField}
        onEditField={() => {}}
      />,
    )

    expect(screen.getByText('CR number')).toBeInTheDocument()
    expect(screen.getByText('1010123456')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /looks right/i })).toBeNull()
    // The confirmed row has no button; the two open rows each have one.
    expect(screen.queryByTestId('confirm-field-cr_number')).toBeNull()
    const button = screen.getByTestId('confirm-field-company_name')
    expect(button).toHaveTextContent('Use Bean Street Trading Co.')
    await user.click(button)
    expect(onConfirmField).toHaveBeenCalledWith('company_name')
    expect(onConfirmField).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('confirm-field-company_address')).toBeEnabled()
  })

  it('shows the value label, and Change sends edit_field', async () => {
    const user = userEvent.setup()
    const onEditField = vi.fn()
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')
    render(
      <ConfirmFieldsCard
        cardId="confirm-ar"
        payload={{
          ...confirmFieldsCardExample.payload,
          fields: [
            {
              key: 'brand_name_ar',
              label: 'Brand name (Arabic)',
              display: 'بين ستريت',
              source: 'derived',
              confirmed: false,
              evidence: 'brand Bean Street',
              value_label: 'بين ستريت',
            },
          ],
          all_confirmed: false,
        }}
        onConfirmField={() => {}}
        onEditField={onEditField}
      />,
    )
    expect(screen.getByTestId('confirm-field-brand_name_ar')).toHaveTextContent('بين ستريت')
    await user.click(screen.getByTestId('edit-field-brand_name_ar'))
    const input = screen.getByLabelText('Brand name (Arabic)')
    await user.clear(input)
    await user.type(input, 'بِين ستريت{Enter}')
    expect(onEditField).toHaveBeenCalledWith('brand_name_ar', 'بِين ستريت')
  })

  it('shows a tick on confirmed rows and no buttons once all are confirmed', () => {
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')
    const payload = confirmFieldsCardExample.payload
    render(
      <ConfirmFieldsCard
        cardId="confirm-done"
        payload={{
          ...payload,
          fields: payload.fields.map((f) => ({ ...f, confirmed: true })),
          all_confirmed: true,
        }}
        onConfirmField={() => {}}
        onEditField={() => {}}
      />,
    )
    expect(screen.queryAllByTestId(/^confirm-field-/)).toHaveLength(0)
    expect(screen.getAllByLabelText('Confirmed')).toHaveLength(3)
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
        onConfirmField={() => {}}
        onEditField={() => {}}
      />,
    )
    expect(screen.getByText("from: 'specialty coffee kiosk'")).toBeInTheDocument()
  })

  it('renders document evidence without quotes', () => {
    if (confirmFieldsCardExample.card_type !== 'confirm_fields') throw new Error('bad fixture')
    render(
      <ConfirmFieldsCard
        cardId="confirm-doc-evidence"
        payload={{
          ...confirmFieldsCardExample.payload,
          fields: [
            {
              key: 'company_name',
              label: 'Company name',
              display: 'Bean Street Trading Co.',
              source: 'derived',
              confirmed: false,
              evidence: 'Company Profile: company_profile_match.pdf, uploaded 09 Nov 2026 12:00',
            },
          ],
          all_confirmed: false,
        }}
        onConfirmField={() => {}}
        onEditField={() => {}}
      />,
    )
    expect(
      screen.getByText(/from: Company Profile, company_profile_match\.pdf/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/'Company Profile/)).not.toBeInTheDocument()
  })
})
