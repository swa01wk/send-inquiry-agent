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

  it('keeps first-level approval disabled until the documents are decided', () => {
    renderPanel(
      caseDetail({
        first_approval_blockers: [
          'document_pending:brand_profile',
          'expiry_unconfirmed:company_profile',
        ],
      }),
    )
    const form = within(screen.getByTestId('action-approve_first'))
    expect(form.getByRole('button', { name: 'Approve first level' })).toBeDisabled()
    const blockers = within(screen.getByTestId('first-approval-blockers'))
    expect(blockers.getByText('Brand profile: approve or reject it')).toBeInTheDocument()
    expect(blockers.getByText('Company profile: confirm the expiry date')).toBeInTheDocument()
  })

  it('asks for the rejected documents when nothing is ticked', async () => {
    const user = userEvent.setup()
    const base = caseDetail()
    const onAct = renderPanel({
      ...base,
      brief: {
        ...base.brief,
        documents: [
          { ...base.brief.documents[0], approval: 'rejected', approval_remarks: 'Unreadable' },
        ],
      },
    })
    const form = within(screen.getByTestId('action-request_reupload'))
    expect(form.getByTestId('reupload-rejected-hint')).toHaveTextContent('CR certificate')
    await user.click(form.getByRole('button', { name: 'Request re-upload' }))
    expect(onAct).toHaveBeenCalledWith('request_reupload', { doc_types: [], remarks: '' })
  })

  it('sends the rejection remarks when only rejected documents are ticked', async () => {
    // Re-demo flow 1 (10 Nov): ticking the rejected document disabled the button.
    const user = userEvent.setup()
    const base = caseDetail()
    const onAct = renderPanel({
      ...base,
      brief: {
        ...base.brief,
        documents: [
          { ...base.brief.documents[0], approval: 'rejected', approval_remarks: 'Unreadable' },
        ],
      },
    })
    const form = within(screen.getByTestId('action-request_reupload'))
    await user.click(form.getByLabelText('CR certificate'))
    expect(form.getByTestId('reupload-ticked-rejected-hint')).toHaveTextContent(
      'CR certificate: Unreadable',
    )
    const send = form.getByRole('button', { name: 'Request re-upload' })
    expect(send).toBeEnabled()
    await user.click(send)
    expect(onAct).toHaveBeenCalledWith('request_reupload', {
      doc_types: ['cr_certificate'],
      remarks: '',
    })
    // A ticked document that wasn't rejected still needs remarks.
    await user.click(form.getByLabelText('VAT certificate'))
    expect(send).toBeDisabled()
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
    expect(within(blockers).getByText('Authorized Signatory still needed')).toBeInTheDocument()
    expect(within(blockers).getByText('Contacts request still open')).toBeInTheDocument()
    expect(screen.queryByTestId('action-approve')).not.toBeInTheDocument()
  })

  it('has no Remove for contacts (flow v2 V14)', () => {
    vi.spyOn(review, 'listYardiBrands').mockResolvedValue([])
    renderPanel(secondReviewDetail())
    expect(screen.queryByTestId('action-remove_contact')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
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

  describe('flow v2 second level (§3.7)', () => {
    const MALLS = [
      { id: 'riyadh-mall-a', label: 'Riyadh Mall A' },
      { id: 'riyadh-mall-b', label: 'Riyadh Mall B' },
    ]

    function qualified(overrides: Partial<ReturnType<typeof secondReviewDetail>> = {}) {
      return secondReviewDetail({
        legal_actions: ['request_sales_data', 'assign_unit', 'reject'],
        approval_blockers: [],
        lead_approval_blockers: ['unit_not_assigned'],
        assigned_unit: null,
        inquiry_malls: MALLS,
        ...overrides,
      })
    }

    it('assigns the unit with an optional area', async () => {
      const user = userEvent.setup()
      const onAct = renderPanel(qualified())
      const form = within(screen.getByTestId('action-assign_unit'))
      const submit = form.getByTestId('assign-unit-submit')
      expect(submit).toBeDisabled()
      await user.selectOptions(form.getByTestId('assign-unit-mall'), 'riyadh-mall-b')
      await user.type(form.getByTestId('assign-unit-ref'), ' RMB-G-007 ')
      await user.click(submit)
      expect(onAct).toHaveBeenLastCalledWith('assign_unit', {
        mall_id: 'riyadh-mall-b',
        unit_ref: 'RMB-G-007',
      })
      await user.type(form.getByTestId('assign-unit-area'), '95')
      await user.click(submit)
      expect(onAct).toHaveBeenLastCalledWith('assign_unit', {
        mall_id: 'riyadh-mall-b',
        unit_ref: 'RMB-G-007',
        area_sqm: 95,
      })
    })

    it('shows what blocks Approve Lead? until the unit is in', () => {
      renderPanel(qualified())
      const blockers = screen.getByTestId('lead-approval-blockers')
      expect(within(blockers).getByText('Assign the unit first')).toBeInTheDocument()
      expect(screen.queryByTestId('action-approve_lead')).not.toBeInTheDocument()
      expect(screen.queryByTestId('approval-blockers')).not.toBeInTheDocument()
    })

    it('shows the assigned unit and offers Yes and No', async () => {
      const user = userEvent.setup()
      const onAct = renderPanel(
        qualified({
          legal_actions: ['request_sales_data', 'assign_unit', 'approve_lead', 'reject'],
          lead_approval_blockers: [],
          assigned_unit: {
            mall_id: 'riyadh-mall-a',
            unit_ref: 'RMA-G-014',
            area_sqm: 95,
            by: 'rlm_store-central',
            at: '2026-11-14T09:00:00Z',
          },
        }),
      )
      expect(screen.getByTestId('assigned-unit')).toHaveTextContent(
        'Assigned: RMA-G-014 at Riyadh Mall A (95 sq m)',
      )
      expect(screen.getByTestId('assign-unit-submit')).toHaveTextContent('Change unit')
      await user.click(screen.getByTestId('approve-lead-no'))
      expect(onAct).not.toHaveBeenCalled()
      expect(document.activeElement).toBe(screen.getByLabelText('Reason'))
      await user.click(screen.getByTestId('approve-lead-yes'))
      expect(onAct).toHaveBeenCalledWith('approve_lead', {})
    })

    it('keeps the final Approve Lead disabled until the contacts are in', () => {
      const base = secondReviewDetail()
      renderPanel({
        ...base,
        brief: { ...base.brief, status: 'lead_approved', stage_label: 'Lead Approved' },
        legal_actions: ['relink_company', 'relink_brand'],
        approval_blockers: ['missing_contact:billing_contact', 'open_request:contacts'],
      })
      expect(screen.getByTestId('approve-lead-final')).toBeDisabled()
      const blockers = screen.getByTestId('approval-blockers')
      expect(within(blockers).getByText('Before the final Approve Lead')).toBeInTheDocument()
      expect(within(blockers).getByText('Billing Contact still needed')).toBeInTheDocument()
      expect(screen.queryByTestId('action-reject')).not.toBeInTheDocument()
    })

    it('approves the lead once the contacts are in', async () => {
      const user = userEvent.setup()
      const base = secondReviewDetail()
      const onAct = renderPanel({
        ...base,
        brief: { ...base.brief, status: 'lead_approved', stage_label: 'Lead Approved' },
        legal_actions: ['relink_company', 'relink_brand', 'approve'],
        approval_blockers: [],
      })
      const final = screen.getByTestId('approve-lead-final')
      expect(final).toBeEnabled()
      await user.click(final)
      expect(onAct).toHaveBeenCalledWith('approve', {})
    })
  })
})
