import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as dev from '../api/dev'
import * as review from '../api/review'
import { reviewerCentral } from '../review/fixtures'
import { DevHomePage } from './DevHomePage'

vi.mock('../config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../config')>()),
  REVIEWER_CONSOLE: true,
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
