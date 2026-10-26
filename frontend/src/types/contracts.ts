export type Source = 'user' | 'derived' | 'verified' | 'default'

export type Phase =
  | 'existing_account'
  | 'submitted'
  | 'gate'
  | 'collecting'
  | 'verifying'
  | 'documents'
  | 'review'

export type CardType =
  | 'confirm_fields'
  | 'mall_picker'
  | 'verification'
  | 'document_upload'
  | 'review'
  | 'success'
  | 'quick_replies'

export type StepState = 'done' | 'current' | 'upcoming'

export interface ConfirmFieldRow {
  key: string
  label: string
  display: string | null
  source: Source | null
  confirmed: boolean
}

export interface ConfirmFieldsPayload {
  title: string
  fields: ConfirmFieldRow[]
  all_confirmed: boolean
}

export interface MallPickerCity {
  id: string
  label: string
}

export interface MallPickerMall {
  id: string
  name: string
}

export interface MallPickerPayload {
  city: MallPickerCity
  malls: MallPickerMall[]
  selected: string[]
  min_select: number
  /** One mall per inquiry: 1 makes the picker a single choice. */
  max_select: number
}

export interface VerificationEmail {
  masked: string | null
  link_sent: boolean
  verified: boolean
  /** Demo only: stands in for clicking the emailed link. */
  demo_token: string | null
}

export interface VerificationMobile {
  masked: string | null
  code_sent: boolean
  verified: boolean
  attempts_left: number
  code_length: number
}

export interface VerificationPayload {
  email: VerificationEmail
  /** null when only a landline was given: email alone verifies the applicant. */
  mobile: VerificationMobile | null
  all_verified: boolean
}

export interface DraftDocumentRow {
  doc_type: string
  label: string
  required: boolean
  uploaded: boolean
  file_name: string | null
  size_bytes: number | null
}

export interface DocumentUploadPayload {
  docs: DraftDocumentRow[]
  required_uploaded: number
  required_total: number
  allowed_extensions: string[]
  max_mb: number
}

export interface ReviewGroupRow {
  key: string
  label: string
  display: string | null
  source: Source | null
  confirmed: boolean
  required: boolean
}

export interface ReviewGroup {
  title: string
  rows: ReviewGroupRow[]
}

export interface DraftChecks {
  required_filled: number
  required_total: number
  unconfirmed: number
  email_verified: boolean
  mobile_verified: boolean
  /** Every channel that needs it is verified (email always, mobile when given). */
  contact_verified: boolean
  required_docs_uploaded: number
  required_docs_total: number
  terms_accepted: boolean
}

export interface ReviewPayload {
  groups: ReviewGroup[]
  documents: DraftDocumentRow[]
  checks: DraftChecks
  can_submit: boolean
  terms_accepted: boolean
  blockers: string[]
}

export interface SuccessStep {
  label: string
  detail: string
  state: StepState
}

export interface SuccessPayload {
  reference: string
  tracking_url: string
  steps: SuccessStep[]
}

export interface QuickReplyOption {
  label: string
  text: string
  action?: 'send' | 'focus_input'
  placeholder?: string | null
}

export interface QuickRepliesPayload {
  options: QuickReplyOption[]
}

export type UiCard =
  | {
      card_id: string
      card_type: 'confirm_fields'
      message_id: string | null
      payload: ConfirmFieldsPayload
    }
  | {
      card_id: string
      card_type: 'mall_picker'
      message_id: string | null
      payload: MallPickerPayload
    }
  | {
      card_id: string
      card_type: 'verification'
      message_id: string | null
      payload: VerificationPayload
    }
  | {
      card_id: string
      card_type: 'document_upload'
      message_id: string | null
      payload: DocumentUploadPayload
    }
  | {
      card_id: string
      card_type: 'review'
      message_id: string | null
      payload: ReviewPayload
    }
  | {
      card_id: string
      card_type: 'success'
      message_id: string | null
      payload: SuccessPayload
    }
  | {
      card_id: string
      card_type: 'quick_replies'
      message_id: string | null
      payload: QuickRepliesPayload
    }

export interface DraftFieldRow {
  key: string
  label: string
  group: string
  display: string | null
  source: Source | null
  confirmed: boolean
  required: boolean
}

export interface DraftSummary {
  phase: Phase
  fields: DraftFieldRow[]
  documents: DraftDocumentRow[]
  checks: DraftChecks
  can_submit: boolean
  changed_keys: string[]
}

export type ChatRequest =
  | { type: 'message'; text: string }
  | { type: 'action'; action: string; payload: Record<string, unknown> }

export type SseEvent =
  | { event: 'token'; data: { message_id: string; text: string } }
  | { event: 'ui_card'; data: UiCard }
  | { event: 'message_remove'; data: { message_id: string } }
  | { event: 'draft'; data: DraftSummary }
  | { event: 'done'; data: { phase: Phase } }
  | { event: 'error'; data: { code: string; message: string } }

export interface AssistantMessage {
  id: string
  role: 'assistant'
  text: string
}

export interface CreateSessionResponse {
  session_id: string
  messages: AssistantMessage[]
  cards: UiCard[]
  draft: DraftSummary
}
