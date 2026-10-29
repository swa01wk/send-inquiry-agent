import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as callcentre from '../api/callcentre'
import * as dev from '../api/dev'
import * as review from '../api/review'
import * as tenant from '../api/tenant'
import { reviewerCentral } from '../review/fixtures'
import { DevHomePage } from './DevHomePage'

vi.mock('../config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../config')>()),
  REVIEWER_CONSOLE: true,
  CALLCENTRE_CONSOLE: true,
  TENANT_PORTAL: true,
}))

const clock: dev.ClockState = {
  now: '2026-11-02T07:00:00.000Z',
  offset_hours: 0,
  simulated: true,
  timezone: 'Asia/Riyadh',
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DevHomePage />
    </MemoryRouter>,
  )
}

describe('DevHomePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(dev, 'getClock').mockResolvedValue(clock)
    vi.spyOn(review, 'listReviewers').mockResolvedValue([reviewerCentral])
    vi.spyOn(callcentre, 'listStaff').mockResolvedValue([
      {
        id: 'customer-care-1',
        name: 'Sami Al Anazi',
        role: 'customer_care',
        role_label: 'The Cenomi call centre',
      },
    ])
    vi.spyOn(tenant, 'listTenants').mockResolvedValue([
      {
        id: 'T-1001',
        company_name: 'Oasis Coffee Company',
        contact_name: 'Layla Hassan',
        brands: [],
      },
    ])
  })

  it('links every persona, each reviewer queue in one click', async () => {
    renderPage()
    expect(screen.getByRole('link', { name: /Applicant chat/ })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /Dev inbox/ })).toHaveAttribute('href', '/dev/inbox')
    expect(await screen.findByRole('link', { name: /Faisal Al Qahtani/ })).toHaveAttribute(
      'href',
      '/review?as=rlm_store-central',
    )
  })

  it('links the call centre and each tenant', async () => {
    renderPage()
    expect(await screen.findByRole('link', { name: /Sami Al Anazi/ })).toHaveAttribute(
      'href',
      '/callcentre?as=customer-care-1',
    )
    expect(await screen.findByRole('link', { name: /Oasis Coffee Company/ })).toHaveAttribute(
      'href',
      '/tenant?as=T-1001',
    )
  })

  it('shows Riyadh time and advances the clock', async () => {
    const user = userEvent.setup()
    const advance = vi.spyOn(dev, 'advanceClock').mockResolvedValue({
      clock: { ...clock, offset_hours: 48 },
      raised: 1,
      sent: 0,
      resolved: 0,
    })
    renderPage()
    expect(await screen.findByTestId('dev-clock')).toHaveTextContent('10:00')
    await user.click(screen.getByRole('button', { name: '+48 h' }))
    expect(advance).toHaveBeenCalledWith(48)
    expect(await screen.findByTestId('dev-message')).toHaveTextContent('1 raised')
  })

  it('resets only after confirming', async () => {
    const user = userEvent.setup()
    const reset = vi.spyOn(dev, 'resetDemo').mockResolvedValue({ reset: true })
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Reset demo' }))
    expect(reset).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Yes, reset everything' }))
    expect(reset).toHaveBeenCalled()
    expect(await screen.findByTestId('dev-message')).toHaveTextContent('Demo reset')
  })
})
