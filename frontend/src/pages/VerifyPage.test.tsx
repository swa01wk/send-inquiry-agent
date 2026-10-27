import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { VerifyPage } from './VerifyPage'

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/inquiry/verify${search}`]}>
      <Routes>
        <Route path="/inquiry/verify" element={<VerifyPage />} />
        <Route path="/" element={<div>Chat home</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('VerifyPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows verified state and continues into the chat', async () => {
    const user = userEvent.setup()
    vi.spyOn(client, 'verifyEmailLink').mockResolvedValue({
      status: 'verified',
      session_id: 'sess-1',
      email_masked: 's***@example.com',
      resume_token: 'resume-tok',
    })
    vi.spyOn(client, 'resumeSession').mockResolvedValue({
      session_id: 'sess-1',
      messages: [{ id: 'm1', role: 'assistant', text: 'Hi' }],
      cards: [],
      draft: {
        phase: 'verifying',
        fields: [],
        documents: [],
        checks: {
          required_filled: 0,
          required_total: 11,
          unconfirmed: 0,
          email_verified: true,
          mobile_verified: false,
          contact_verified: false,
          required_docs_uploaded: 0,
          required_docs_total: 2,
          terms_accepted: false,
        },
        can_submit: false,
        changed_keys: [],
      },
    })

    renderAt('?t=verify-tok')
    await waitFor(() => {
      expect(screen.getByText(/email verified/i)).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /continue your inquiry/i }))
    await waitFor(() => {
      expect(screen.getByText('Chat home')).toBeInTheDocument()
    })
    expect(client.resumeSession).toHaveBeenCalledWith('resume-tok')
  })

  it('shows token_expired guidance', async () => {
    vi.spyOn(client, 'verifyEmailLink').mockRejectedValue(
      Object.assign(
        new Error('This verification link has expired. Ask for a new one in the chat.'),
        {
          code: 'token_expired',
        },
      ),
    )
    renderAt('?t=old')
    await waitFor(() => {
      expect(screen.getByText(/resend link/i)).toBeInTheDocument()
    })
  })
})
