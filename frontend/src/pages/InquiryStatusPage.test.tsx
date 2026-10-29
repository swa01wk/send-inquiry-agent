import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { InquiryStatusPage } from './InquiryStatusPage'

describe('InquiryStatusPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders stages for a valid tracking token', async () => {
    vi.spyOn(client, 'fetchInquiryStatus').mockResolvedValue({
      reference: 'GEO-STR-123456',
      status: 'under_review',
      summary:
        'Your inquiry was submitted and is waiting for review. Current owner: Regional Leasing Manager (Store).',
      submitted_at: '2026-10-28T09:00:00.000Z',
      steps: [],
      stages: [
        { key: 'submitted', label: 'Inquiry submitted', state: 'done' },
        { key: 'first_review', label: 'First review', state: 'current' },
        { key: 'second_review', label: 'Second review', state: 'upcoming' },
        { key: 'outcome', label: 'Outcome', state: 'upcoming' },
      ],
      current_stage: 'first_review',
      owner_role: 'Regional Leasing Manager (Store)',
      waiting_on_you: [],
      last_change: '2026-10-28T09:00:00.000Z',
    })

    render(
      <MemoryRouter initialEntries={['/inquiry/status/GEO-STR-123456?t=track-tok']}>
        <Routes>
          <Route path="/inquiry/status/:reference" element={<InquiryStatusPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('GEO-STR-123456')).toBeInTheDocument()
    })
    expect(screen.getByText(/waiting for review/i)).toBeInTheDocument()
    expect(screen.getByText('First review')).toBeInTheDocument()
  })

  it.each([
    {
      status: 'approved' as const,
      summary: "Approved — we're passing your details to the leasing team",
    },
    {
      status: 'sent_to_yardi' as const,
      summary: 'Approved — your details are with the leasing team for a proposal',
    },
  ])('shows final approval summary when status is $status', async ({ status, summary }) => {
    vi.spyOn(client, 'fetchInquiryStatus').mockResolvedValue({
      reference: 'GEO-STR-999999',
      status,
      summary,
      submitted_at: '2026-10-28T09:00:00.000Z',
      steps: [],
      stages: [
        { key: 'submitted', label: 'Inquiry submitted', state: 'done' },
        { key: 'first_review', label: 'First review', state: 'done' },
        { key: 'second_review', label: 'Lead — second review', state: 'done' },
        { key: 'outcome', label: 'Outcome', state: 'current' },
      ],
      current_stage: 'outcome',
      owner_role: 'Leasing team',
      waiting_on_you: [],
      last_change: '2026-10-28T09:00:00.000Z',
    })

    render(
      <MemoryRouter initialEntries={['/inquiry/status/GEO-STR-999999?t=track-tok']}>
        <Routes>
          <Route path="/inquiry/status/:reference" element={<InquiryStatusPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(summary)).toBeInTheDocument()
    })
  })
})
