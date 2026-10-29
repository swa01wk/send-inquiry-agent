import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as callcentre from '../api/callcentre'
import type { CreateSessionResponse } from '../types/contracts'
import { CallCentrePage } from './CallCentrePage'

const staffMember: callcentre.StaffMember = {
  id: 'customer-care-1',
  name: 'Sami Al Anazi',
  role: 'customer_care',
  role_label: 'The Cenomi call centre',
}

const sessionResponse = {
  session_id: 'sess-assisted-1',
  messages: [{ id: 'm1', role: 'assistant' as const, text: 'Hello' }],
  cards: [],
  draft: {
    phase: 'collecting' as const,
    fields: [],
    documents: [],
    checks: {
      required_filled: 0,
      required_total: 0,
      unconfirmed: 0,
      email_verified: false,
      mobile_verified: false,
      contact_verified: false,
      required_docs_uploaded: 0,
      required_docs_total: 0,
      terms_accepted: false,
    },
    can_submit: false,
    changed_keys: [],
    follow_on_of: null,
  },
} satisfies CreateSessionResponse

const handoff: callcentre.HandoffItem = {
  case_id: 'case-abc',
  inquiry_id: 'inq-1',
  short_ref: 'GEO-STR-999999',
  reason: 'complex_case',
  reason_label: 'Complex case',
  summary: 'Applicant asked to speak to someone.',
  created_at: '2026-03-01T10:30:00Z',
}

function SearchEcho() {
  const location = useLocation()
  return <div data-testid="url-search">{location.search}</div>
}

function HomeCapture() {
  const location = useLocation()
  return (
    <div data-testid="home">
      {(location.state as { resumed?: CreateSessionResponse } | null)?.resumed?.session_id ??
        'none'}
    </div>
  )
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/callcentre"
          element={
            <>
              <SearchEcho />
              <CallCentrePage />
            </>
          }
        />
        <Route path="/" element={<HomeCapture />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Call centre console', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.sessionStorage.clear()
    vi.spyOn(callcentre, 'listStaff').mockResolvedValue([staffMember])
  })

  it('signs in with the mock picker', async () => {
    const user = userEvent.setup()
    vi.spyOn(callcentre, 'listHandoffs').mockResolvedValue([])
    renderAt('/callcentre')
    const picker = await screen.findByLabelText('Staff member')
    await user.selectOptions(picker, 'customer-care-1')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByTestId('callcentre-signed-in')).toHaveTextContent('Sami Al Anazi')
    expect(screen.getByTestId('callcentre-signed-in')).toHaveTextContent('The Cenomi call centre')
    expect(window.sessionStorage.getItem('cenomi.staffId')).toBe('customer-care-1')
  })

  it('signs in from ?as= and keeps e2eScenario', async () => {
    vi.spyOn(callcentre, 'listHandoffs').mockResolvedValue([])
    renderAt('/callcentre?as=customer-care-1&e2eScenario=demo-flow')
    expect(await screen.findByTestId('callcentre-signed-in')).toHaveTextContent('Sami')
    expect(window.sessionStorage.getItem('cenomi.staffId')).toBe('customer-care-1')
    await waitFor(() => {
      expect(screen.getByTestId('url-search')).toHaveTextContent('e2eScenario=demo-flow')
    })
    expect(screen.getByTestId('url-search').textContent).not.toContain('as=')
  })

  it('starts a new inquiry and navigates with resumed session', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.staffId', 'customer-care-1')
    vi.spyOn(callcentre, 'listHandoffs').mockResolvedValue([])
    const newInquiry = vi.spyOn(callcentre, 'newInquiry').mockResolvedValue(sessionResponse)
    renderAt('/callcentre')
    await user.click(await screen.findByTestId('callcentre-new-inquiry'))
    await waitFor(() => expect(newInquiry).toHaveBeenCalledWith('customer-care-1'))
    expect(await screen.findByTestId('home')).toHaveTextContent('sess-assisted-1')
  })

  it('lists handoffs and opens one in the chat', async () => {
    const user = userEvent.setup()
    window.sessionStorage.setItem('cenomi.staffId', 'customer-care-1')
    vi.spyOn(callcentre, 'listHandoffs').mockResolvedValue([handoff])
    const openHandoff = vi
      .spyOn(callcentre, 'openHandoff')
      .mockResolvedValue({ ...sessionResponse, session_id: 'sess-handoff-1' })
    renderAt('/callcentre')
    const row = await screen.findByTestId('handoff-case-abc')
    expect(row).toHaveTextContent('GEO-STR-999999')
    expect(row).toHaveTextContent('Complex case')
    expect(row).toHaveTextContent('Applicant asked to speak to someone.')
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => expect(openHandoff).toHaveBeenCalledWith('customer-care-1', 'case-abc'))
    expect(await screen.findByTestId('home')).toHaveTextContent('sess-handoff-1')
  })

  it('returns to sign-in when the staff id is unknown', async () => {
    window.sessionStorage.setItem('cenomi.staffId', 'customer-care-1')
    vi.spyOn(callcentre, 'listHandoffs').mockRejectedValue(
      Object.assign(new Error('Sign in as a call-centre or Guest Service user.'), {
        code: 'unknown_staff',
      }),
    )
    renderAt('/callcentre')
    expect(await screen.findByTestId('callcentre-sign-in')).toBeInTheDocument()
    expect(window.sessionStorage.getItem('cenomi.staffId')).toBeNull()
  })
})
