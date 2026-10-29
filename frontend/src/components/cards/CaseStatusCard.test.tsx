import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { CaseStatusPayload } from '../../types/contracts'
import { CaseStatusCard } from './CaseStatusCard'

const sample: CaseStatusPayload = {
  reference: 'GEO-STR-123456',
  status: 'under_review',
  stage: 'first_review',
  stage_label: 'First review',
  status_headline: null,
  owner_role: 'Regional Leasing Manager (Store)',
  last_change: '2026-10-28T09:00:00.000Z',
  open_requests: [
    {
      id: 'req-1',
      kind: 'reupload',
      label: 'Re-upload documents',
      remarks: 'Brand profile is blurry.',
      doc_types: ['brand_profile'],
      requested_at: '2026-10-28T10:00:00.000Z',
    },
  ],
  outcome: null,
  outcome_remarks: null,
  next_step: 'Re-upload the requested documents, then press Resubmit.',
}

describe('CaseStatusCard', () => {
  it('shows stage, owner, open requests, and next step', () => {
    render(<CaseStatusCard payload={sample} />)

    expect(screen.getByTestId('case-status-card')).toBeInTheDocument()
    expect(screen.getByText('First review')).toBeInTheDocument()
    expect(screen.getByText(/Regional Leasing Manager \(Store\)/)).toBeInTheDocument()
    expect(screen.getByText('Re-upload documents')).toBeInTheDocument()
    expect(screen.getByText('Brand profile is blurry.')).toBeInTheDocument()
    expect(screen.getByText(/Re-upload the requested documents/)).toBeInTheDocument()
  })

  it('shows outcome when set', () => {
    render(
      <CaseStatusCard
        payload={{
          ...sample,
          open_requests: [],
          outcome: 'rejected',
          outcome_remarks: 'Does not fit the mall mix.',
          next_step: 'You may send a new inquiry.',
        }}
      />,
    )

    expect(screen.getByText('Rejected')).toBeInTheDocument()
    expect(screen.getByText('Does not fit the mall mix.')).toBeInTheDocument()
  })

  it.each([
    {
      status: 'approved' as const,
      headline: "Approved — we're passing your details to the leasing team",
    },
    {
      status: 'sent_to_yardi' as const,
      headline: 'Approved — your details are with the leasing team for a proposal',
    },
  ])('shows final approval headline when status is $status', ({ status, headline }) => {
    render(
      <CaseStatusCard
        payload={{
          ...sample,
          status,
          stage: 'outcome',
          stage_label: 'Outcome',
          status_headline: headline,
          open_requests: [],
          outcome: 'approved',
          next_step: 'Nothing is needed from you right now.',
        }}
      />,
    )

    expect(screen.getAllByText(headline).length).toBeGreaterThanOrEqual(1)
  })
})
