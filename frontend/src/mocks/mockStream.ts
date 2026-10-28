import {
  confirmFieldsCardExample,
  documentUploadCardExample,
  draftComplete,
  draftMidway,
  mallPickerCardExample,
  verificationCardExample,
  reviewCardExample,
  successCardExample,
} from './fixtures'
import { mockDraft, patchMockDraft } from './mockStreamState'
import type { ChatRequest, DraftSummary, SseEvent, UiCard } from '../types/contracts'

const STEP_DELAY_MS = 700

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const t = setTimeout(resolve, ms)
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(t)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

async function streamBotReply(
  messageId: string,
  chunks: string[],
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  for (const text of chunks) {
    await sleep(STEP_DELAY_MS / 2, signal)
    onEvent({ event: 'token', data: { message_id: messageId, text } })
  }
}

function withDraft(draft: DraftSummary, changed_keys: string[] = []): SseEvent {
  patchMockDraft(draft)
  return { event: 'draft', data: { ...draft, changed_keys } }
}

function qrEvent(messageId: string, labels: Array<[string, string]>): SseEvent {
  const card: UiCard = {
    card_id: `qr-${Date.now()}`,
    card_type: 'quick_replies',
    message_id: messageId,
    payload: {
      options: labels.map(([label, text]) => ({ label, text })),
    },
  }
  return { event: 'ui_card', data: card }
}

let messageCounter = 0
function nextMessageId(): string {
  messageCounter += 1
  return `mock-m-${messageCounter}`
}

export async function replayMockChat(
  request: ChatRequest,
  onEvent: (event: SseEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const text =
    request.type === 'message'
      ? request.text.trim()
      : request.type === 'action'
        ? `[action:${request.action}]`
        : ''

  const mid = nextMessageId()

  if (request.type === 'action' && request.action === 'select_malls') {
    const ids = (request.payload.mall_ids as string[]) ?? []
    const mallPayload =
      mallPickerCardExample.card_type === 'mall_picker'
        ? mallPickerCardExample.payload
        : { malls: [] as { id: string; name: string }[] }
    const names = mallPayload.malls.filter((m) => ids.includes(m.id)).map((m) => m.name)
    const draft: DraftSummary = {
      ...mockDraft,
      phase: 'collecting',
      fields: mockDraft.fields.map((f) =>
        f.key === 'malls'
          ? { ...f, display: names.join(', '), source: 'user', confirmed: true }
          : f,
      ),
      changed_keys: ['malls'],
    }
    await streamBotReply(
      mid,
      ['Nice picks. Who should our leasing team contact about this?'],
      onEvent,
      signal,
    )
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (request.type === 'action' && request.action === 'verify_email') {
    await streamBotReply(mid, ['Email confirmed. Now the SMS code, please.'], onEvent, signal)
    if (verificationCardExample.card_type === 'verification') {
      const payload = verificationCardExample.payload
      onEvent({
        event: 'ui_card',
        data: {
          ...verificationCardExample,
          payload: { ...payload, email: { ...payload.email, verified: true, demo_token: null } },
        },
      })
    }
    onEvent({ event: 'done', data: { phase: mockDraft.phase } })
    return
  }

  if (request.type === 'action' && request.action === 'submit_otp') {
    const code = String(request.payload.code ?? '')
    if (code === '1234') {
      const draft: DraftSummary = {
        ...mockDraft,
        phase: 'documents',
        checks: {
          ...mockDraft.checks,
          email_verified: true,
          mobile_verified: true,
          contact_verified: true,
        },
        changed_keys: [],
      }
      await streamBotReply(mid, ["You're verified, thank you!"], onEvent, signal)
      const m2 = nextMessageId()
      await streamBotReply(
        m2,
        [
          'Last step before review: documents. Company Profile and Brand Profile are required; the rest are optional but help our team move faster.',
        ],
        onEvent,
        signal,
      )
      if (documentUploadCardExample.card_type === 'document_upload') {
        onEvent({
          event: 'ui_card',
          data: {
            ...documentUploadCardExample,
            message_id: m2,
            payload: {
              ...documentUploadCardExample.payload,
              docs: draft.documents.map((d) => ({ ...d })),
            },
          },
        })
      }
      onEvent(withDraft(draft))
      onEvent({ event: 'done', data: { phase: draft.phase } })
    } else {
      await streamBotReply(
        mid,
        ["Hmm, that code didn't match. You have 2 attempts left."],
        onEvent,
        signal,
      )
      if (verificationCardExample.card_type === 'verification') {
        const payload = verificationCardExample.payload
        onEvent({
          event: 'ui_card',
          data: {
            ...verificationCardExample,
            payload: {
              ...payload,
              mobile: payload.mobile && { ...payload.mobile, attempts_left: 2 },
            },
          },
        })
      }
      onEvent({ event: 'done', data: { phase: mockDraft.phase } })
    }
    return
  }

  if (request.type === 'action' && request.action === 'accept_and_submit') {
    const draft: DraftSummary = { ...draftComplete, phase: 'submitted', changed_keys: [] }
    await streamBotReply(mid, ['Thank you, Ahmed! Your inquiry is in.'], onEvent, signal)
    onEvent({
      event: 'ui_card',
      data: { ...successCardExample, message_id: mid },
    })
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: 'submitted' } })
    return
  }

  const lower = text.toLowerCase()

  if (
    lower.includes('1010123456') ||
    lower.includes('my cr number is') ||
    lower === 'i have my cr number'
  ) {
    const draft: DraftSummary = {
      ...draftMidway,
      phase: 'collecting',
      changed_keys: ['company_name', 'company_address'],
    }
    await streamBotReply(
      mid,
      [
        "Thanks! I checked: there's no existing account for this CR, so you're all set to send an inquiry.",
      ],
      onEvent,
      signal,
    )
    const m2 = nextMessageId()
    await streamBotReply(
      m2,
      ["Here's what your CR record shows. Is it still correct?"],
      onEvent,
      signal,
    )
    onEvent({
      event: 'ui_card',
      data: { ...confirmFieldsCardExample, message_id: m2 },
    })
    onEvent(qrEvent(m2, [["Yes, that's correct", "Yes, that's correct"]]))
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower.includes("yes, that's correct") || lower.includes('yes, that’s correct')) {
    const draft: DraftSummary = {
      ...mockDraft,
      phase: 'collecting',
      fields: mockDraft.fields.map((f) =>
        f.key === 'company_name' || f.key === 'company_address' ? { ...f, confirmed: true } : f,
      ),
      checks: { ...mockDraft.checks, unconfirmed: Math.max(0, mockDraft.checks.unconfirmed - 2) },
      changed_keys: ['company_name', 'company_address'],
    }
    await streamBotReply(
      mid,
      ["Perfect. Now the fun part: tell me about your brand and what you'd like to open."],
      onEvent,
      signal,
    )
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower.includes('bean street') && lower.includes('kiosk')) {
    const draft: DraftSummary = {
      ...mockDraft,
      phase: 'collecting',
      fields: mockDraft.fields.map((f) => {
        if (f.key === 'brand_name_en')
          return { ...f, display: 'Bean Street', source: 'user', confirmed: true }
        if (f.key === 'brand_name_ar')
          return { ...f, display: 'بين ستريت', source: 'derived', confirmed: false }
        if (f.key === 'unit_type')
          return { ...f, display: 'Specialty', source: 'derived', confirmed: false }
        if (f.key === 'sales_category')
          return { ...f, display: 'Food & Beverage · Café', source: 'derived', confirmed: false }
        return f
      }),
      checks: { ...mockDraft.checks, required_filled: mockDraft.checks.required_filled + 4 },
      changed_keys: ['brand_name_en', 'brand_name_ar', 'unit_type', 'sales_category'],
    }
    await streamBotReply(
      mid,
      ['Specialty coffee, lovely. That works well in busy mall walkways.'],
      onEvent,
      signal,
    )
    const m2 = nextMessageId()
    await streamBotReply(m2, ["Here's what I picked up. Anything to change?"], onEvent, signal)
    onEvent({
      event: 'ui_card',
      data: {
        card_id: 'brand-confirm',
        card_type: 'confirm_fields',
        message_id: m2,
        payload: {
          title: "Here's what I picked up. Anything to change?",
          fields: draft.fields
            .filter((f) =>
              ['brand_name_en', 'brand_name_ar', 'unit_type', 'sales_category'].includes(f.key),
            )
            .map(({ key, label, display, source, confirmed }) => ({
              key,
              label,
              display,
              source,
              confirmed,
              evidence: null,
            })),
          all_confirmed: false,
        },
      },
    })
    onEvent(qrEvent(m2, [['All good', 'All good']]))
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower === 'all good') {
    const draft: DraftSummary = {
      ...mockDraft,
      fields: mockDraft.fields.map((f) =>
        ['brand_name_ar', 'unit_type', 'sales_category'].includes(f.key)
          ? { ...f, confirmed: true }
          : f,
      ),
      changed_keys: ['brand_name_ar', 'unit_type', 'sales_category'],
    }
    await streamBotReply(
      mid,
      [
        'Great. Where would you like to open, and roughly how much space and budget do you have in mind?',
      ],
      onEvent,
      signal,
    )
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower.includes('riyadh') && lower.includes('250')) {
    const draft: DraftSummary = {
      ...mockDraft,
      fields: mockDraft.fields.map((f) => {
        if (f.key === 'area')
          return { ...f, display: '25 – 35 sqm', source: 'derived', confirmed: false }
        if (f.key === 'rent')
          return { ...f, display: 'Up to SAR 250,000 / year', source: 'user', confirmed: true }
        if (f.key === 'lease') return { ...f, display: '3 years', source: 'user', confirmed: true }
        return f
      }),
      changed_keys: ['area', 'rent', 'lease'],
    }
    await streamBotReply(
      mid,
      [
        "Got it. I've set the area to 25–35 sqm, rent up to SAR 250,000 per year and a 3-year lease. You can change these anytime.",
      ],
      onEvent,
      signal,
    )
    const m2 = nextMessageId()
    await streamBotReply(
      m2,
      ['Here are our malls in Riyadh. Pick as many as you like:'],
      onEvent,
      signal,
    )
    if (mallPickerCardExample.card_type === 'mall_picker') {
      onEvent({
        event: 'ui_card',
        data: {
          ...mallPickerCardExample,
          message_id: m2,
          payload: { ...mallPickerCardExample.payload, selected: [] },
        },
      })
    }
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower.includes('ahmed') && lower.includes('beanstreet')) {
    const draft: DraftSummary = {
      ...mockDraft,
      phase: 'verifying',
      fields: mockDraft.fields.map((f) => {
        if (f.key === 'first_name')
          return { ...f, display: 'Ahmed', source: 'user', confirmed: true }
        if (f.key === 'last_name')
          return { ...f, display: 'Al-Harbi', source: 'user', confirmed: true }
        if (f.key === 'email')
          return { ...f, display: 'ahmed@beanstreet.sa', source: 'user', confirmed: true }
        if (f.key === 'mobile')
          return { ...f, display: '+966 55 123 4567', source: 'user', confirmed: true }
        return f
      }),
      changed_keys: ['first_name', 'last_name', 'email', 'mobile'],
    }
    await streamBotReply(
      mid,
      ["Thanks, Ahmed! +966 55 123 4567 is a mobile number, so I'll use it for verification."],
      onEvent,
      signal,
    )
    const m2 = nextMessageId()
    await streamBotReply(
      m2,
      ["I've emailed you a verification link and texted a 4-digit code to your mobile:"],
      onEvent,
      signal,
    )
    onEvent({ event: 'ui_card', data: { ...verificationCardExample, message_id: m2 } })
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  if (lower.includes('what do i need')) {
    await streamBotReply(
      mid,
      [
        'Just a few details about your brand and the space you want, a contact number for verification, and two documents: your company profile and brand profile. Other documents are optional.',
      ],
      onEvent,
      signal,
    )
    onEvent({ event: 'done', data: { phase: mockDraft.phase } })
    return
  }

  if (lower.includes("don't have it handy") || lower.includes('dont have it handy')) {
    await streamBotReply(
      mid,
      [
        "No problem. When you have your CR number, share it here and I'll look up your company details.",
      ],
      onEvent,
      signal,
    )
    onEvent({ event: 'done', data: { phase: mockDraft.phase } })
    return
  }

  if (lower.includes('continue to review')) {
    const missing = mockDraft.documents.filter((d) => d.required && !d.uploaded)
    if (missing.length) {
      await streamBotReply(
        mid,
        [
          `Almost there. I still need your ${missing.map((d) => d.label).join(' and ')} before we can submit.`,
        ],
        onEvent,
        signal,
      )
      onEvent({ event: 'done', data: { phase: mockDraft.phase } })
      return
    }
    const draft: DraftSummary = { ...draftComplete, phase: 'review', changed_keys: [] }
    await streamBotReply(
      mid,
      [
        "Here's everything in one place. Check the details, accept the terms, and submit when you're ready.",
      ],
      onEvent,
      signal,
    )
    onEvent({ event: 'ui_card', data: { ...reviewCardExample, message_id: mid } })
    onEvent(withDraft(draft))
    onEvent({ event: 'done', data: { phase: draft.phase } })
    return
  }

  // Default friendly reply
  await streamBotReply(
    mid,
    [
      "Thanks for your message. Share your CR number when you're ready, or pick one of the suggestions below.",
    ],
    onEvent,
    signal,
  )
  onEvent(
    qrEvent(mid, [
      ['I have my CR number', 'I have my CR number'],
      ["I don't have it handy", "I don't have it handy"],
      ['What do I need to get started?', 'What do I need to get started?'],
    ]),
  )
  onEvent({ event: 'done', data: { phase: mockDraft.phase } })
}
