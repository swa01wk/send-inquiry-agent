import {
  basicInfoReviewCardExample,
  confirmFieldsCardExample,
  defaultMockSessionCards,
  documentUploadCardExample,
  draftComplete,
  draftEmpty,
  draftMidway,
  existingCrChoiceCardExample,
  mallPickerCardExample,
  MOCK_WELCOME_MESSAGES,
  quickRepliesCardExample,
  reviewCardExample,
  sendLinkCardExample,
  signInPromptCardExample,
  successCardExample,
  verificationCardExample,
} from '../fixtures'
import type { FeScenario } from './types'
import type { CreateSessionResponse, DraftSummary, UiCard } from '../../types/contracts'

function session(
  cards: CreateSessionResponse['cards'],
  draft: DraftSummary,
  messages = MOCK_WELCOME_MESSAGES,
): CreateSessionResponse {
  return {
    session_id: 'mock-session',
    messages,
    cards,
    draft: JSON.parse(JSON.stringify(draft)) as DraftSummary,
  }
}

function cardSession(card: UiCard, draft: DraftSummary): CreateSessionResponse {
  const msgId = card.message_id ?? 'm-static'
  return session([card], draft, [
    { id: 'welcome-1', role: 'assistant', text: 'Here is the card for this test scenario.' },
    { id: msgId, role: 'assistant', text: 'Please use the card below.' },
  ])
}

const confirmDraft = draftMidway

export const feScenarioDefinitions: FeScenario[] = [
  {
    name: 'confirm-fields',
    session: cardSession({ ...confirmFieldsCardExample, message_id: 'm-static' }, confirmDraft),
    turns: [
      {
        when: { type: 'action', action: 'confirm_card' },
        events: [
          {
            event: 'draft',
            data: {
              ...confirmDraft,
              fields: confirmDraft.fields.map((f) =>
                f.key === 'company_name' || f.key === 'company_address'
                  ? { ...f, confirmed: true }
                  : f,
              ),
              changed_keys: ['company_name', 'company_address'],
            },
          },
          { event: 'done', data: { phase: 'collecting' } },
        ],
      },
    ],
  },
  {
    name: 'mall-picker',
    session: cardSession(
      {
        ...mallPickerCardExample,
        message_id: 'm-static',
        payload:
          mallPickerCardExample.card_type === 'mall_picker'
            ? { ...mallPickerCardExample.payload, selected: [] }
            : mallPickerCardExample.payload,
      } as UiCard,
      draftMidway,
    ),
    turns: [
      {
        when: { type: 'action', action: 'select_malls' },
        events: [
          { event: 'token', data: { message_id: 'm-reply', text: 'Nice picks.' } },
          {
            event: 'draft',
            data: {
              ...draftMidway,
              fields: draftMidway.fields.map((f) =>
                f.key === 'malls'
                  ? { ...f, display: 'Riyadh Mall A', source: 'user', confirmed: true }
                  : f,
              ),
              changed_keys: ['malls'],
            },
          },
          { event: 'done', data: { phase: 'collecting' } },
        ],
      },
    ],
  },
  {
    name: 'verification',
    session: cardSession(
      { ...verificationCardExample, message_id: 'm-static' },
      {
        ...draftMidway,
        phase: 'verifying',
      },
    ),
    turns: [
      {
        when: { type: 'action', action: 'verify_email' },
        events: [
          { event: 'token', data: { message_id: 'm-reply', text: 'Email confirmed.' } },
          {
            event: 'ui_card',
            data: (() => {
              if (verificationCardExample.card_type !== 'verification') {
                return verificationCardExample
              }
              const payload = verificationCardExample.payload
              return {
                ...verificationCardExample,
                message_id: 'm-static',
                payload: {
                  ...payload,
                  email: { ...payload.email, verified: true, demo_token: null },
                },
              }
            })(),
          },
          { event: 'done', data: { phase: 'verifying' } },
        ],
      },
    ],
  },
  {
    name: 'documents-partial',
    session: cardSession(
      {
        ...documentUploadCardExample,
        message_id: 'm-static',
        payload: {
          ...documentUploadCardExample.payload,
          docs: draftMidway.documents,
          required_uploaded: 0,
        },
      } as UiCard,
      { ...draftMidway, phase: 'documents' },
    ),
  },
  {
    name: 'documents-complete',
    session: cardSession(
      {
        ...documentUploadCardExample,
        message_id: 'm-static',
        payload: {
          ...documentUploadCardExample.payload,
          docs: draftComplete.documents,
          required_uploaded: 2,
        },
      } as UiCard,
      { ...draftComplete, phase: 'documents' },
    ),
  },
  {
    name: 'documents-on-file',
    session: cardSession(
      {
        ...documentUploadCardExample,
        message_id: 'm-static',
        payload: {
          ...documentUploadCardExample.payload,
          docs: draftMidway.documents.map((d) =>
            d.doc_type === 'company_profile'
              ? { ...d, on_file: true, uploaded: false, file_name: null }
              : d,
          ),
          required_uploaded: 0,
        },
      } as UiCard,
      { ...draftMidway, phase: 'documents' },
    ),
  },
  {
    name: 'review',
    session: cardSession({ ...reviewCardExample, message_id: 'm-static' }, draftComplete),
  },
  {
    name: 'success',
    session: cardSession(
      { ...successCardExample, message_id: 'm-static' },
      {
        ...draftComplete,
        phase: 'submitted',
      },
    ),
  },
  {
    name: 'quick-replies',
    session: session([{ ...quickRepliesCardExample, message_id: 'welcome-2' }], draftEmpty),
    turns: [
      {
        when: { type: 'message', textEquals: 'I have my CR number' },
        events: [
          {
            event: 'token',
            data: { message_id: 'm-reply', text: 'Great — share your CR when ready.' },
          },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
  {
    name: 'basic-info-review',
    session: cardSession(basicInfoReviewCardExample, draftMidway),
    turns: [
      {
        when: { type: 'action', action: 'proceed_basic_info' },
        events: [{ event: 'done', data: { phase: 'collecting' } }],
      },
    ],
  },
  {
    name: 'send-link',
    session: cardSession(sendLinkCardExample, draftMidway),
    turns: [
      {
        when: { type: 'action', action: 'send_application_link' },
        events: [
          {
            event: 'ui_card',
            data: {
              ...sendLinkCardExample,
              payload: {
                ...sendLinkCardExample.payload,
                can_send: false,
                sent_to_masked: 's***@oasis.sa',
              },
            } as UiCard,
          },
          { event: 'done', data: { phase: 'collecting' } },
        ],
      },
    ],
  },
  {
    name: 'existing-cr-choice',
    session: cardSession(existingCrChoiceCardExample, draftEmpty),
    turns: [
      {
        when: { type: 'action', action: 'existing_cr_choice' },
        events: [
          {
            event: 'ui_card',
            data: {
              ...existingCrChoiceCardExample,
              payload: { ...existingCrChoiceCardExample.payload, chosen: 'continue' },
            } as UiCard,
          },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
  {
    name: 'sign-in-prompt',
    session: cardSession(signInPromptCardExample, draftEmpty),
  },
  {
    name: 'draft-panel',
    session: session(defaultMockSessionCards(), draftMidway),
  },
  {
    name: 'stream-error-retry',
    session: session([], draftEmpty),
    turns: [
      {
        when: { type: 'message', textEquals: 'trigger error' },
        events: [
          { event: 'error', data: { code: 'agent_error', message: 'Mock stream failed once.' } },
        ],
      },
      {
        when: { type: 'message', textEquals: 'trigger error' },
        events: [
          { event: 'token', data: { message_id: 'm-ok', text: 'Back online.' } },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
  {
    name: 'stream-message-remove',
    session: session([], draftEmpty),
    turns: [
      {
        when: { type: 'any' },
        events: [
          { event: 'token', data: { message_id: 'm-bad', text: 'This reply will be retracted.' } },
          { event: 'message_remove', data: { message_id: 'm-bad' } },
          { event: 'token', data: { message_id: 'm-good', text: 'Here is the corrected reply.' } },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
  {
    name: 'stream-turn-in-progress',
    session: session([], draftEmpty),
    turns: [
      {
        when: { type: 'any' },
        events: [],
        behavior: 'reject_turn_in_progress',
      },
      {
        when: { type: 'any' },
        events: [
          { event: 'token', data: { message_id: 'm-ok', text: 'Ready when you are.' } },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
  {
    name: 'stream-dropped-connection',
    session: session([], draftEmpty),
    turns: [
      {
        when: { type: 'any' },
        events: [{ event: 'token', data: { message_id: 'm-cut', text: 'Starting…' } }],
        behavior: 'abort_mid_stream',
      },
      {
        when: { type: 'any' },
        events: [
          { event: 'token', data: { message_id: 'm-ok', text: 'Connection restored.' } },
          { event: 'done', data: { phase: 'gate' } },
        ],
      },
    ],
  },
]
