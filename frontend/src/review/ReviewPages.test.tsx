import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as review from '../api/review'
import { attentionList, caseDetail, queueItem, reviewerCentral, stalledItem } from './fixtures'
import { ReviewCasePage } from './ReviewCasePage'
import { ReviewQueuePage } from './ReviewQueuePage'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/review" element={<ReviewQueuePage />} />
        <Route path="/review/cases/:reference" element={<ReviewCasePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Reviewer console', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.sessionStorage.clear()
    vi.spyOn(review, 'listReviewers').mockResolvedValue([reviewerCentral])
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([]))
  })

  it('signs in with the mock picker and shows the queue', async () => {
    const user = userEvent.setup()
    const listCases = vi.spyOn(review, 'listCases').mockResolvedValue([queueItem])
    renderAt('/review')
    const picker = await screen.findByLabelText('Reviewer')
    await screen.findByRole('option', { name: /Faisal Al Qahtani/ })
    await user.selectOptions(picker, 'rlm_store-central')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByTestId('signed-in-reviewer')).toHaveTextContent(
      'Regional Leasing Manager (Store)',
    )
    const row = await screen.findByTestId('queue-row-GEO-STR-123456')
    expect(within(row).getByRole('link', { name: 'GEO-STR-123456' })).toHaveAttribute(
      'href',
      '/review/cases/GEO-STR-123456',
    )
    expect(within(row).getByText('You')).toBeInTheDocument()
    expect(listCases).toHaveBeenCalledWith('rlm_store-central', undefined)
    expect(window.sessionStorage.getItem('cenomi.reviewerId')).toBe('rlm_store-central')

    await user.selectOptions(screen.getByLabelText('Waiting on'), 'applicant')
    await waitFor(() =>
      expect(listCases).toHaveBeenLastCalledWith('rlm_store-central', 'applicant'),
    )
  })

  it('shows an empty queue', async () => {
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'listCases').mockResolvedValue([])
    renderAt('/review')
    expect(await screen.findByTestId('queue-empty')).toBeInTheDocument()
  })

  it('asks for sign-in before opening a case', () => {
    renderAt('/review/cases/GEO-STR-123456')
    expect(screen.getByRole('link', { name: 'Sign in as a reviewer' })).toBeInTheDocument()
  })

  it('shows the brief, sources, documents and timeline', async () => {
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'getCase').mockResolvedValue(caseDetail())
    renderAt('/review/cases/GEO-STR-123456')
    expect(await screen.findByTestId('case-stage')).toHaveTextContent('First review')
    expect(screen.getByText('Regional Leasing Manager (Store) · Central')).toBeInTheDocument()
    expect(screen.getByText('Verified (CR) · confirmed')).toBeInTheDocument()
    expect(screen.getByText('Derived · confirmed')).toBeInTheDocument()
    expect(screen.getByText('from: “we sell specialty coffee”')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'cr.pdf' })).toBeInTheDocument()
    expect(screen.getByTestId('checklist')).toHaveTextContent('Check the CR certificate')
    expect(screen.getByTestId('timeline')).toHaveTextContent('Routed to Regional Leasing Manager')
  })

  it('applies an action and shows the updated case', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'getCase').mockResolvedValue(caseDetail())
    const after = caseDetail({ legal_actions: [] })
    after.brief = { ...after.brief, status: 'second_review', stage_label: 'Lead — second review' }
    const act = vi.spyOn(review, 'actOnCase').mockResolvedValue(after)
    renderAt('/review/cases/GEO-STR-123456')
    await user.click(await screen.findByRole('button', { name: 'Approve first level' }))
    expect(act).toHaveBeenCalledWith('rlm_store-central', 'GEO-STR-123456', 'approve_first', {})
    expect(await screen.findByTestId('case-stage')).toHaveTextContent('Lead — second review')
    expect(screen.getByTestId('no-actions')).toBeInTheDocument()
  })

  it('shows the API error when an action is refused', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'getCase').mockResolvedValue(caseDetail())
    vi.spyOn(review, 'actOnCase').mockRejectedValue(
      new review.ReviewApiError(409, 'illegal_transition', 'That case has moved on.'),
    )
    renderAt('/review/cases/GEO-STR-123456')
    await user.click(await screen.findByRole('button', { name: 'Approve first level' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That case has moved on.')
  })

  it('says when a case is outside the queues', async () => {
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'getCase').mockRejectedValue(
      new review.ReviewApiError(404, 'case_not_found', 'No such case in your queues.'),
    )
    renderAt('/review/cases/GEO-STR-999999')
    expect(await screen.findByText('This case is not in your queues.')).toBeInTheDocument()
  })

  it('shows the Needs attention count on the queue', async () => {
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'listCases').mockResolvedValue([queueItem])
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([stalledItem()]))
    renderAt('/review')
    expect(await screen.findByTestId('attention-badge')).toHaveTextContent('1')
    expect(screen.getByTestId('attention-link')).toHaveAttribute('href', '/review/attention')
  })

  it('labels how the inquiry came in', async () => {
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
    vi.spyOn(review, 'listCases').mockResolvedValue([{ ...queueItem, channel: 'existing_tenant' }])
    renderAt('/review')
    expect(await screen.findByTestId('channel-label')).toHaveTextContent('Existing tenant')
  })

  it('signs in from ?as= (the dev landing page)', async () => {
    vi.spyOn(review, 'listCases').mockResolvedValue([queueItem])
    renderAt('/review?as=rlm_store-central')
    expect(await screen.findByTestId('signed-in-reviewer')).toHaveTextContent('Faisal')
    expect(window.sessionStorage.getItem('cenomi.reviewerId')).toBe('rlm_store-central')
  })
})
