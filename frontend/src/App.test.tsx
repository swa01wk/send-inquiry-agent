import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { draftEmpty, quickRepliesCardExample } from './mocks/fixtures'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          session_id: 'test-session',
          messages: [
            { id: 'welcome-1', role: 'assistant', text: 'Welcome' },
            { id: 'welcome-2', role: 'assistant', text: 'CR question' },
          ],
          cards: [quickRepliesCardExample],
          draft: draftEmpty,
        }),
      }),
    )
  })

  it('shows the page frame from the design spec', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Welcome')).toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: /send an inquiry/i })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /leasing assistant chat/i })).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: /inquiry draft/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /العربية/i })).toBeInTheDocument()
  })
})
