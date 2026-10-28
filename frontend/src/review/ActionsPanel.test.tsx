import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as review from '../api/review'
import { ActionsPanel } from './ActionsPanel'
import { caseDetail, secondReviewDetail } from './fixtures'

function renderPanel(detail = caseDetail(), onAct = vi.fn()) {
  render(
    <ActionsPanel
      detail={detail}
      reviewerId="rlm_store-central"
      busy={false}
      error={null}
      onAct={onAct}
    />,
  )
  return onAct
}

describe('ActionsPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders only the legal actions', () => {
    renderPanel()
    expect(screen.getByTestId('action-approve_first')).toBeInTheDocument()
    expect(screen.getByTestId('action-request_reupload')).toBeInTheDocument()
    expect(screen.getByTestId('action-reject')).toBeInTheDocument()
    expect(screen.queryByTestId('action-approve')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-requests')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-yardi')).not.toBeInTheDocument()
    expect(screen.queryByTestId('action-remove_contact')).not.toBeInTheDocument()
  })

  it('says so when nothing is open', () => {
    renderPanel(caseDetail({ legal_actions: [] }))
    expect(screen.getByTestId('no-actions')).toBeInTheDocument()
  })

  it('needs documents and remarks before requesting a re-upload', async () => {
    const user = userEvent.setup()
    const onAct = renderPanel()
    const form = within(screen.getByTestId('action-request_reupload'))
    const send = form.getByRole('button', { name: 'Request re-upload' })
    expect(send).toBeDisabled()
    await user.click(form.getByLabelText('VAT certificate'))
    expect(send).toBeDisabled()
    await user.type(form.getByLabelText('Remarks for the applicant'), '  The VAT page is cut off ')
    await user.click(send)
    expect(onAct).toHaveBeenCalledWith('request_reupload', {
      doc_types: ['vat_certificate'],
      remarks: 'The VAT page is cut off',
    })
  })

  it('needs a reason and remarks before rejecting', async () => {
    const user = userEvent.setup()
    const onAct = renderPanel()
    const form = within(screen.getByTestId('action-reject'))
    const reject = form.getByRole('button', { name: 'Reject' })
    await user.type(form.getByLabelText('Remarks for the applicant'), 'No space this year')
    expect(reject).toBeDisabled()
    await user.selectOptions(form.getByLabelText('Reason'), 'no_space')
    await user.click(reject)
    expect(onAct).toHaveBeenCalledWith('reject', {
      remarks: 'No space this year',
      reason_category: 'no_space',
    })
  })

  it('lists what blocks final approval in plain words', () => {
    renderPanel(secondReviewDetail())
    const blockers = screen.getByTestId('approval-blockers')
    expect(within(blockers).getByText('Authorized signatory missing')).toBeInTheDocument()
    expect(within(blockers).getByText('Contacts request still open')).toBeInTheDocument()
    expect(screen.queryByTestId('action-approve')).not.toBeInTheDocument()
  })

  it('removes a contact by role', async () => {
    const user = userEvent.setup()
    vi.spyOn(review, 'listYardiBrands').mockResolvedValue([])
    const onAct = renderPanel(secondReviewDetail())
    const form = within(screen.getByTestId('action-remove_contact'))
    await user.selectOptions(form.getByLabelText('Contact'), 'billing_contact')
    await user.click(form.getByRole('button', { name: 'Remove' }))
    expect(onAct).toHaveBeenCalledWith('remove_contact', { role: 'billing_contact' })
  })

  it('searches Yardi and links a company', async () => {
    const user = userEvent.setup()
    const search = vi
      .spyOn(review, 'searchYardiCompanies')
      .mockResolvedValue([{ id: 'YC-1001', name: 'Bean Street Trading Co.' }])
    const onAct = renderPanel(secondReviewDetail())
    const form = within(screen.getByTestId('action-yardi'))
    expect(form.getByTestId('yardi-linked')).toHaveTextContent('Company: not linked')
    // Prefilled with the company name from the brief.
    expect(form.getByLabelText('Search Yardi companies')).toHaveValue('Bean Street Trading Co.')
    await user.click(form.getByRole('button', { name: 'Search' }))
    expect(search).toHaveBeenCalledWith('rlm_store-central', 'Bean Street Trading Co.')
    await user.selectOptions(await form.findByLabelText('Company'), 'YC-1001')
    await user.click(form.getByRole('button', { name: 'Link company' }))
    expect(onAct).toHaveBeenCalledWith('relink_company', { company_id: 'YC-1001' })
  })

  it("offers the linked company's brands", async () => {
    const user = userEvent.setup()
    const brands = vi.spyOn(review, 'listYardiBrands').mockResolvedValue([
      { id: 'YB-2001', name: 'Bean Street', source: 'lease' },
      { id: 'YB-2002', name: 'Bean Street Express', source: 'proposal' },
    ])
    const base = secondReviewDetail()
    const onAct = renderPanel({
      ...base,
      brief: { ...base.brief, yardi: { ...base.brief.yardi, company_id: 'YC-1001' } },
    })
    await waitFor(() => expect(brands).toHaveBeenCalledWith('rlm_store-central', 'YC-1001'))
    const form = within(screen.getByTestId('action-yardi'))
    await user.selectOptions(form.getByLabelText('Brand'), 'YB-2002')
    await user.click(form.getByRole('button', { name: 'Link brand' }))
    expect(onAct).toHaveBeenCalledWith('relink_brand', { brand_id: 'YB-2002' })
  })
})
