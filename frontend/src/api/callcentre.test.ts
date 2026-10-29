import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { newInquiry } from './callcentre'

vi.mock('../config', () => ({
  API_BASE: 'http://test.local',
  E2E_MODE: false,
}))

describe('callcentre API', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            session_id: 's1',
            messages: [],
            cards: [],
            draft: {},
          }),
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends X-Staff-Id when starting a new inquiry', async () => {
    await newInquiry('customer-care-1')
    expect(fetch).toHaveBeenCalledWith('http://test.local/api/callcentre/inquiries', {
      method: 'POST',
      headers: { 'X-Staff-Id': 'customer-care-1' },
    })
  })

  it('throws errors with backend codes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        json: () =>
          Promise.resolve({
            error: { code: 'unknown_staff', message: 'Sign in as call-centre staff.' },
          }),
      }),
    )
    await expect(newInquiry('bad-id')).rejects.toMatchObject({
      code: 'unknown_staff',
      message: 'Sign in as call-centre staff.',
    })
  })
})
