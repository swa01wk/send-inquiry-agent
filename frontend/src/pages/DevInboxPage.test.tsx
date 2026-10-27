import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { DevInboxPage } from './DevInboxPage'

describe('DevInboxPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('lists outbox messages with links', async () => {
    vi.spyOn(client, 'fetchOutbox').mockResolvedValue([
      {
        id: '1',
        inquiry_id: 'inq-1',
        channel: 'email',
        to: 'sara@beanstreet.example',
        template: 'email_verification_link',
        kind: 'action_required',
        subject: 'Verify your email',
        body: 'Click the link',
        links: ['http://localhost/inquiry/verify?t=abc'],
        created_at: '2026-10-28T10:00:00.000Z',
      },
    ])

    render(
      <MemoryRouter>
        <DevInboxPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/email_verification_link/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('link', { name: /verify\?t=abc/i })).toHaveAttribute(
      'href',
      'http://localhost/inquiry/verify?t=abc',
    )
  })

  it('clears the outbox', async () => {
    const user = userEvent.setup()
    const fetchSpy = vi.spyOn(client, 'fetchOutbox').mockResolvedValue([])
    const clearSpy = vi.spyOn(client, 'clearOutbox').mockResolvedValue()

    render(
      <MemoryRouter>
        <DevInboxPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: /^clear$/i }))
    await waitFor(() => {
      expect(clearSpy).toHaveBeenCalled()
    })
  })
})
