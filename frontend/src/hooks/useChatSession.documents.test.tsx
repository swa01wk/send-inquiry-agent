import { renderHook, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import * as client from '../api/client'
import * as stream from '../api/stream'
import { documentUploadCardExample } from '../mocks/fixtures'
import { ChatProvider } from '../state/chatStore'
import type { DraftSummary } from '../types/contracts'
import { useChatSession } from './useChatSession'

function wrapper({ children }: { children: ReactNode }) {
  return <ChatProvider>{children}</ChatProvider>
}

const baseDraft = (): DraftSummary => ({
  phase: 'documents',
  fields: [],
  documents: [],
  checks: {
    required_filled: 10,
    required_total: 11,
    unconfirmed: 0,
    email_verified: true,
    mobile_verified: true,
    contact_verified: true,
    required_docs_uploaded: 1,
    required_docs_total: 2,
    terms_accepted: false,
  },
  can_submit: false,
  changed_keys: [],
  follow_on_of: null,
})

const docCard =
  documentUploadCardExample.card_type === 'document_upload' ? documentUploadCardExample : null

describe('useChatSession documents_updated', () => {
  beforeEach(() => {
    vi.spyOn(client, 'createSession').mockResolvedValue({
      session_id: 'sess-1',
      messages: [],
      cards: [],
      draft: baseDraft(),
    })
    vi.spyOn(stream, 'streamChat').mockResolvedValue('ok')
  })

  it('sends documents_updated once when required uploads reach the total', async () => {
    const { result } = renderHook(() => useChatSession(), { wrapper })
    await act(async () => {
      await Promise.resolve()
    })

    if (!docCard) throw new Error('fixture')

    const afterFirst: DraftSummary = {
      ...baseDraft(),
      checks: { ...baseDraft().checks, required_docs_uploaded: 1 },
    }
    const afterSecond: DraftSummary = {
      ...baseDraft(),
      checks: { ...baseDraft().checks, required_docs_uploaded: 2 },
    }

    vi.spyOn(client, 'uploadDocument')
      .mockResolvedValueOnce({
        document: { doc_type: 'company_profile', file_name: 'a.pdf', size_bytes: 10 },
        card: docCard,
        draft: afterFirst,
      })
      .mockResolvedValueOnce({
        document: { doc_type: 'brand_profile', file_name: 'b.pdf', size_bytes: 10 },
        card: docCard,
        draft: afterSecond,
      })

    await act(async () => {
      await result.current.uploadDocument('company_profile', new File(['x'], 'a.pdf'))
    })
    expect(stream.streamChat).not.toHaveBeenCalled()

    await act(async () => {
      await result.current.uploadDocument('brand_profile', new File(['x'], 'b.pdf'))
    })
    expect(stream.streamChat).toHaveBeenCalledTimes(1)
    expect(stream.streamChat).toHaveBeenCalledWith(
      'sess-1',
      { type: 'action', action: 'documents_updated', payload: {} },
      expect.any(Function),
      expect.any(AbortSignal),
    )
  })

  it('does not send documents_updated for optional-only uploads when required are done', async () => {
    const doneDraft: DraftSummary = {
      ...baseDraft(),
      checks: { ...baseDraft().checks, required_docs_uploaded: 2 },
    }
    vi.spyOn(client, 'createSession').mockResolvedValue({
      session_id: 'sess-2',
      messages: [],
      cards: [],
      draft: doneDraft,
    })

    const { result } = renderHook(() => useChatSession(), { wrapper })
    await act(async () => {
      await Promise.resolve()
    })

    if (!docCard) throw new Error('fixture')

    vi.spyOn(client, 'uploadDocument').mockResolvedValue({
      document: { doc_type: 'vat_certificate', file_name: 'vat.pdf', size_bytes: 10 },
      card: docCard,
      draft: doneDraft,
    })

    await act(async () => {
      await result.current.uploadDocument('vat_certificate', new File(['x'], 'vat.pdf'))
    })
    expect(stream.streamChat).not.toHaveBeenCalled()
  })
})
