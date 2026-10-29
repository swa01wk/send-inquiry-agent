import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as review from '../api/review'
import type { SseEvent } from '../types/contracts'
import { ActionsPanel } from './ActionsPanel'
import { caseDetail, secondReviewDetail } from './fixtures'
import { prefillFromSuggestion } from './prefillFromSuggestion'
import { ReviewerAssistantPanel } from './ReviewerAssistantPanel'

function wireAssistantAndActions(detail = caseDetail(), onAct = vi.fn()) {
  let prefill: ReturnType<typeof prefillFromSuggestion> | undefined

  const tree = () => (
    <>
      <ReviewerAssistantPanel
        reviewerId="rlm_store-central"
        reference={detail.brief.reference}
        onUseSuggestion={(payload) => {
          prefill = prefillFromSuggestion(payload)
          view.rerender(tree())
        }}
      />
      <ActionsPanel
        detail={detail}
        reviewerId="rlm_store-central"
        busy={false}
        error={null}
        prefill={prefill}
        onAct={onAct}
      />
    </>
  )

  const view = render(tree())

  return { onAct, user: userEvent.setup() }
}

describe('ReviewerAssistantPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows streamed assistant text', async () => {
    const stream = vi
      .spyOn(review, 'streamReviewerAssistant')
      .mockImplementation(async (_reviewerId, _ref, _text, onEvent) => {
        onEvent({ event: 'token', data: { message_id: 'm1', text: 'Hello ' } })
        onEvent({ event: 'token', data: { message_id: 'm1', text: 'reviewer.' } })
        return 'ok'
      })

    const user = userEvent.setup()
    render(
      <ReviewerAssistantPanel
        reviewerId="rlm_store-central"
        reference="GEO-STR-123456"
        onUseSuggestion={() => undefined}
      />,
    )
    await user.type(screen.getByLabelText('Message'), 'Summarise this case.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(stream).toHaveBeenCalled())
    expect(await screen.findByText('Hello reviewer.')).toBeInTheDocument()
  })

  it('Use fills reject remarks without calling actOnCase', async () => {
    vi.spyOn(review, 'streamReviewerAssistant').mockImplementation(
      async (_reviewerId, _ref, _text, onEvent) => {
        const card: SseEvent = {
          event: 'ui_card',
          data: {
            card_id: 's1',
            card_type: 'reviewer_suggestion',
            message_id: 'm1',
            payload: {
              kind: 'rejection_remarks',
              action: 'reject',
              payload: { remarks: 'No space in this mall this year.' },
              text: 'No space in this mall this year.',
            },
          },
        }
        onEvent({ event: 'token', data: { message_id: 'm1', text: 'Draft:' } })
        onEvent(card)
        return 'ok'
      },
    )
    const actOnCase = vi.spyOn(review, 'actOnCase')

    const { onAct, user } = wireAssistantAndActions()
    await user.type(screen.getByLabelText('Message'), 'Draft a rejection.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    const suggestion = await screen.findByTestId('reviewer-suggestion')
    await user.click(within(suggestion).getByRole('button', { name: 'Use' }))

    const rejectForm = within(screen.getByTestId('action-reject'))
    expect(rejectForm.getByLabelText('Remarks for the applicant')).toHaveValue(
      'No space in this mall this year.',
    )
    expect(onAct).not.toHaveBeenCalled()
    expect(actOnCase).not.toHaveBeenCalled()
  })

  it('Use on relink_company selects the company in Yardi pickers', async () => {
    vi.spyOn(review, 'streamReviewerAssistant').mockImplementation(
      async (_reviewerId, _ref, _text, onEvent) => {
        onEvent({
          event: 'ui_card',
          data: {
            card_id: 's2',
            card_type: 'reviewer_suggestion',
            message_id: 'm2',
            payload: {
              kind: 'yardi_company',
              action: 'relink_company',
              payload: { company_id: 'YC-1001' },
              text: 'Bean Street Trading Co. (id YC-1001) — First word matches.',
            },
          },
        })
        return 'ok'
      },
    )

    const { user } = wireAssistantAndActions(secondReviewDetail())
    await user.type(screen.getByLabelText('Message'), 'Find Yardi company.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    const suggestion = await screen.findByTestId('reviewer-suggestion')
    await user.click(within(suggestion).getByRole('button', { name: 'Use' }))

    const yardi = within(screen.getByTestId('action-yardi'))
    await waitFor(() => expect(yardi.getByLabelText('Company')).toHaveValue('YC-1001'))
    expect(yardi.getByLabelText('Company')).toHaveTextContent('Bean Street Trading Co.')
  })
})
