import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { BriefContact, BriefDocument } from '../api/review'
import { ContactDecisions } from './ContactDecisions'
import { DocumentDecisions } from './DocumentDecisions'

function doc(overrides: Partial<BriefDocument> = {}): BriefDocument {
  return {
    doc_type: 'company_profile',
    label: 'Company Profile',
    required: true,
    uploaded: true,
    file_id: 'co-1',
    file_name: 'company.pdf',
    size_bytes: 100,
    uploaded_at: '2026-11-05T09:00:00.000Z',
    replaced_versions: 0,
    approval: 'pending',
    approval_remarks: null,
    expiry_tracked: true,
    expiry: '2027-11-05',
    expiry_extracted: '2027-11-05',
    expiry_confirmed: null,
    expiry_status: 'valid',
    review_status: 'done',
    suggested_reject_remarks: null,
    ...overrides,
  }
}

function renderDocs(documents: BriefDocument[], canDecide = true) {
  const onAct = vi.fn()
  render(
    <DocumentDecisions
      documents={documents}
      canDecide={canDecide}
      busy={false}
      onAct={onAct}
      onOpen={vi.fn()}
    />,
  )
  return onAct
}

describe('DocumentDecisions', () => {
  it('approves a valid document with its file id', async () => {
    const user = userEvent.setup()
    const onAct = renderDocs([doc()])
    expect(screen.getByTestId('doc-expiry-status-company_profile')).toHaveTextContent('Valid until')
    await user.click(screen.getByTestId('doc-approve-company_profile'))
    expect(onAct).toHaveBeenCalledWith('approve_document', {
      doc_type: 'company_profile',
      file_id: 'co-1',
    })
  })

  it('preselects Reject for an expired document and keeps Approve disabled', async () => {
    const user = userEvent.setup()
    const remark = 'This document expired on 06 Oct 2026. Please upload a current one.'
    const onAct = renderDocs([
      doc({
        expiry: '2026-10-06',
        expiry_extracted: '2026-10-06',
        expiry_status: 'expired',
        suggested_reject_remarks: remark,
      }),
    ])
    expect(screen.getByTestId('doc-expiry-status-company_profile')).toHaveTextContent('Expired on')
    expect(screen.getByTestId('doc-approve-company_profile')).toBeDisabled()
    expect(screen.getByLabelText('Remarks (needed to reject)')).toHaveValue(remark)
    expect(onAct).not.toHaveBeenCalled()
    await user.click(screen.getByTestId('doc-reject-company_profile'))
    expect(onAct).toHaveBeenCalledWith('reject_document', {
      doc_type: 'company_profile',
      file_id: 'co-1',
      remarks: remark,
    })
  })

  it('needs an expiry date before approving when none is known', async () => {
    const user = userEvent.setup()
    const onAct = renderDocs([
      doc({
        expiry: null,
        expiry_extracted: null,
        expiry_status: 'unknown',
        review_status: 'pending',
      }),
    ])
    expect(screen.getByTestId('doc-approve-company_profile')).toBeDisabled()
    expect(screen.getByText(/document check didn’t answer/)).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('doc-expiry-company_profile'), {
      target: { value: '2027-03-31' },
    })
    await user.click(screen.getByRole('button', { name: 'Save date' }))
    expect(onAct).toHaveBeenCalledWith('confirm_document_expiry', {
      doc_type: 'company_profile',
      file_id: 'co-1',
      expiry_date: '2027-03-31',
    })
  })

  it('shows decisions read-only to a role that does not decide', () => {
    renderDocs([doc({ approval: 'rejected', approval_remarks: 'Old logo' })], false)
    expect(screen.getByTestId('doc-approval-company_profile')).toHaveTextContent(
      'Rejected: Old logo',
    )
    expect(screen.queryByTestId('doc-approve-company_profile')).not.toBeInTheDocument()
    expect(screen.queryByTestId('doc-reject-company_profile')).not.toBeInTheDocument()
  })
})

function contact(overrides: Partial<BriefContact> = {}): BriefContact {
  return {
    role: 'billing_contact',
    label: 'Billing Contact',
    name: 'Omar Saleh',
    email: 'omar@beanstreet.example',
    phone: '+966551234567',
    same_as_primary: false,
    contact_id: 'ct_1',
    approval: 'pending',
    approval_remarks: null,
    approved_by: null,
    added_by: 'tenant',
    ...overrides,
  }
}

describe('ContactDecisions', () => {
  it('approves and rejects (with remarks) a pending contact', async () => {
    const user = userEvent.setup()
    const onAct = vi.fn()
    render(<ContactDecisions contacts={[contact()]} canDecide busy={false} onAct={onAct} />)
    const reject = screen.getByTestId('contact-reject-billing_contact')
    expect(reject).toBeDisabled()
    await user.type(screen.getByLabelText('Remarks (needed to reject)'), 'Use the finance mailbox')
    await user.click(reject)
    expect(onAct).toHaveBeenCalledWith('reject_contact', {
      contact_id: 'ct_1',
      remarks: 'Use the finance mailbox',
    })
    await user.click(screen.getByTestId('contact-approve-billing_contact'))
    expect(onAct).toHaveBeenCalledWith('approve_contact', { contact_id: 'ct_1' })
  })

  it('shows the chips read-only to the final reviewer', () => {
    render(
      <ContactDecisions
        contacts={[contact({ approval: 'approved' })]}
        canDecide={false}
        busy={false}
        onAct={vi.fn()}
      />,
    )
    expect(screen.getByTestId('contact-approval-billing_contact')).toHaveTextContent('Approved')
    expect(screen.queryByTestId('contact-approve-billing_contact')).not.toBeInTheDocument()
  })
})
