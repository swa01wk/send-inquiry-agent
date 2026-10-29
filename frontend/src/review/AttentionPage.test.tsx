import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as review from '../api/review'
import type { SseEvent } from '../types/contracts'
import { AttentionPage } from './AttentionPage'
import { attentionList, reminderItem, stalledItem } from './fixtures'

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/review/attention']}>
      <Routes>
        <Route path="/review/attention" element={<AttentionPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AttentionPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.sessionStorage.clear()
    window.sessionStorage.setItem('cenomi.reviewerId', 'rlm_store-central')
  })

  it('asks for sign-in first', () => {
    window.sessionStorage.clear()
    renderPage()
    expect(screen.getByRole('link', { name: 'Sign in as a reviewer' })).toBeInTheDocument()
  })

  it('lists flags and reminders with their age against the target', async () => {
    vi.spyOn(review, 'listAttention').mockResolvedValue(
      attentionList([stalledItem(), reminderItem()]),
    )
    renderPage()
    const stalled = await screen.findByTestId('attention-stalled_review-GEO-STR-123456')
    expect(within(stalled).getByTestId('attention-age')).toHaveTextContent(
      'Waiting 49 h (target 48 h)',
    )
    expect(within(stalled).getByRole('link', { name: 'GEO-STR-123456' })).toHaveAttribute(
      'href',
      '/review/cases/GEO-STR-123456',
    )
    expect(screen.getByTestId('attention-counts')).toHaveTextContent('2 open')
  })

  it('drafts with the assistant, Use fills the textarea, and does not approve', async () => {
    const user = userEvent.setup()
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([reminderItem()]))
    const approve = vi.spyOn(review, 'approveAttention')
    vi.spyOn(review, 'streamReviewerAssistant').mockImplementation(
      async (_reviewerId, _ref, text, onEvent) => {
        expect(text).toContain('Add company contacts')
        const card: SseEvent = {
          event: 'ui_card',
          data: {
            card_id: 's-rem',
            card_type: 'reviewer_suggestion',
            message_id: 'm1',
            payload: {
              kind: 'tenant_reminder',
              action: '',
              payload: {
                remarks: 'Friendly reminder: please add your company contacts.',
              },
              text: 'Friendly reminder: please add your company contacts.',
            },
          },
        }
        onEvent(card)
        return 'ok'
      },
    )
    renderPage()
    const card = await screen.findByTestId('attention-applicant_reminder-GEO-STR-123456')
    await user.click(within(card).getByTestId('attention-draft-assistant'))
    const draft = await within(card).findByTestId('attention-assistant-draft')
    expect(draft).toHaveTextContent('Friendly reminder: please add your company contacts.')
    await user.click(within(card).getByTestId('attention-use-draft'))
    expect(within(card).getByLabelText('Reminder to the applicant')).toHaveValue(
      'Friendly reminder: please add your company contacts.',
    )
    expect(approve).not.toHaveBeenCalled()
  })

  it('approves a reminder as drafted, without sending the unchanged text', async () => {
    const user = userEvent.setup()
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([reminderItem()]))
    const approve = vi
      .spyOn(review, 'approveAttention')
      .mockResolvedValue(reminderItem({ status: 'sent' }))
    renderPage()
    const card = await screen.findByTestId('attention-applicant_reminder-GEO-STR-123456')
    await user.click(within(card).getByRole('button', { name: 'Approve and send' }))
    expect(approve).toHaveBeenCalledWith('rlm_store-central', 'att_reminder1', undefined)
    expect(await screen.findByRole('status')).toHaveTextContent('Reminder sent for GEO-STR-123456')
  })

  it('sends the edited text and reports a hold for quiet hours', async () => {
    const user = userEvent.setup()
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([reminderItem()]))
    const approve = vi
      .spyOn(review, 'approveAttention')
      .mockResolvedValue(reminderItem({ status: 'held', send_after: '2026-11-06T05:00:00.000Z' }))
    renderPage()
    const card = await screen.findByTestId('attention-applicant_reminder-GEO-STR-123456')
    const box = within(card).getByLabelText('Reminder to the applicant')
    await user.clear(box)
    await user.type(box, 'Please add your contacts.')
    await user.click(within(card).getByRole('button', { name: 'Approve and send' }))
    expect(approve).toHaveBeenCalledWith(
      'rlm_store-central',
      'att_reminder1',
      'Please add your contacts.',
    )
    expect(await screen.findByRole('status')).toHaveTextContent('held until')
  })

  it('dismisses only with a reason', async () => {
    const user = userEvent.setup()
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([stalledItem()]))
    const dismiss = vi
      .spyOn(review, 'dismissAttention')
      .mockResolvedValue(stalledItem({ status: 'dismissed', dismissed_reason: 'already_handled' }))
    renderPage()
    const card = await screen.findByTestId('attention-stalled_review-GEO-STR-123456')
    const button = within(card).getByRole('button', { name: 'Dismiss' })
    expect(button).toBeDisabled()
    await user.selectOptions(within(card).getByLabelText('Dismiss because'), 'already_handled')
    await user.click(button)
    expect(dismiss).toHaveBeenCalledWith('rlm_store-central', 'att_stalled1', 'already_handled')
  })

  it('says when nothing needs attention', async () => {
    vi.spyOn(review, 'listAttention').mockResolvedValue(attentionList([]))
    renderPage()
    expect(await screen.findByTestId('attention-empty')).toBeInTheDocument()
  })
})
