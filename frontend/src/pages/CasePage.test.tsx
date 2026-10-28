import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { draftEmpty } from '../mocks/fixtures'
import type { CreateSessionResponse } from '../types/contracts'
import { CasePage } from './CasePage'

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/inquiry/case${search}`]}>
      <Routes>
        <Route path="/inquiry/case" element={<CasePage />} />
        <Route path="/" element={<div>Chat home</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

const sessionPayload: CreateSessionResponse = {
  session_id: 'sess-case-1',
  messages: [{ id: 'm1', role: 'assistant', text: 'Welcome back' }],
  cards: [],
  draft: draftEmpty,
}

describe('CasePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('opens the case and navigates into the chat', async () => {
    vi.spyOn(client, 'openCase').mockResolvedValue(sessionPayload)

    renderAt('?t=case-tok')
    await waitFor(() => {
      expect(screen.getByText('Chat home')).toBeInTheDocument()
    })
    expect(client.openCase).toHaveBeenCalledWith('case-tok')
  })

  it('shows token_expired guidance', async () => {
    vi.spyOn(client, 'openCase').mockRejectedValue(
      Object.assign(new Error('This link has expired. Use your tracking link.'), {
        code: 'token_expired',
      }),
    )
    renderAt('?t=old')
    await waitFor(() => {
      expect(screen.getByText(/track your inquiry/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/this link has expired/i)).toBeInTheDocument()
  })
})
