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
})
