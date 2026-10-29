import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { BasicInfoReviewPayload } from '../../types/contracts'
import { BasicInfoReviewCard } from './BasicInfoReviewCard'

const basePayload: BasicInfoReviewPayload = {
  title: 'Check your details',
  started_by: 'the Cenomi call centre',
  rows: [
    {
      key: 'company_name',
      label: 'Company name',
      display: 'Oasis Coffee',
      source: 'staff',
      confirmed: false,
      required: true,
    },
  ],
  missing: ['Email'],
  can_proceed: false,
  proceeded: false,
}

describe('BasicInfoReviewCard', () => {
  it('shows started by, missing list, and disabled proceed', () => {
    render(
      <BasicInfoReviewCard
        payload={basePayload}
        onEditField={() => undefined}
        onProceed={() => undefined}
      />,
    )
    expect(screen.getByText('Started by the Cenomi call centre')).toBeInTheDocument()
    expect(screen.getByText(/Still needed: Email/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /proceed/i })).toBeDisabled()
  })

  it('fires proceed when enabled', async () => {
    const user = userEvent.setup()
    const onProceed = vi.fn()
    render(
      <BasicInfoReviewCard
        payload={{ ...basePayload, missing: [], can_proceed: true }}
        onEditField={() => undefined}
        onProceed={onProceed}
      />,
    )
    await user.click(screen.getByRole('button', { name: /proceed/i }))
    expect(onProceed).toHaveBeenCalled()
  })

  it('edit saves field value', async () => {
    const user = userEvent.setup()
    const onEditField = vi.fn()
    render(
      <BasicInfoReviewCard
        payload={basePayload}
        onEditField={onEditField}
        onProceed={() => undefined}
      />,
    )
    await user.click(screen.getByRole('button', { name: /edit/i }))
    const input = screen.getByRole('textbox', { name: /company name/i })
    await user.clear(input)
    await user.type(input, 'New Co')
    await user.click(screen.getByRole('button', { name: /save/i }))
    expect(onEditField).toHaveBeenCalledWith('company_name', 'New Co')
  })

  it('done state hides actions', () => {
    render(
      <BasicInfoReviewCard
        payload={{ ...basePayload, proceeded: true, can_proceed: true }}
        onEditField={() => undefined}
        onProceed={() => undefined}
      />,
    )
    expect(screen.getByText('Basic information confirmed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /proceed/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
  })
})
