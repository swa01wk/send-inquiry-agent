export type Source = 'user' | 'derived' | 'verified' | 'staff' | 'default'

export type Phase =
  'existing_account' | 'submitted' | 'gate' | 'collecting' | 'verifying' | 'documents' | 'review'

export type CardType =
  | 'confirm_fields'
  | 'mall_picker'
  | 'verification'
  | 'document_upload'
  | 'review'
  | 'success'
  | 'quick_replies'
  | 'form_mode'
  | 'handoff'
  | 'case_status'
  | 'contacts'
  | 'sales_data_upload'
  | 'reviewer_suggestion'
  | 'basic_info_review'
  | 'send_link'
  | 'existing_cr_choice'
  | 'sign_in_prompt'

export type StepState = 'done' | 'current' | 'upcoming'

export interface ConfirmFieldRow {
  key: string
  label: string
  display: string | null
  source: Source | null
  confirmed: boolean
  evidence: string | null
}

export interface HandoffPayload {
  phone: string
  email: string
  hours: string
  short_ref: string
  case_id: string
  reason: string
}

export interface ConfirmFieldsPayload {
  title: string
  fields: ConfirmFieldRow[]
  all_confirmed: boolean
}

export interface BasicInfoRow {
  key: string
  label: string
  display: string | null
  source: Source | null
  confirmed: boolean
  required: boolean
}

export interface BasicInfoReviewPayload {
  title: string
  started_by: string | null
  rows: BasicInfoRow[]
  missing: string[]
  can_proceed: boolean
  proceeded: boolean
}

export interface SendLinkPayload {
  email_masked: string | null
  can_send: boolean
  missing: string[]
  sent_to_masked?: string | null
}

export interface ExistingCrChoiceOption {
  value: 'sign_in' | 'continue'
  label: string
}

export interface ExistingCrChoicePayload {
  cr_number: string
  company_name: string | null
  options: ExistingCrChoiceOption[]
  chosen?: 'sign_in' | 'continue' | null
}

export interface SignInPromptPayload {
  message: string
  sign_in_url: string
  button_label: string
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
  /** ISO time while resend cooldown or hourly cap applies; else null. */
  resend_available_at: string | null
}

export interface VerificationMobile {
  masked: string | null
  code_sent: boolean
  verified: boolean
  attempts_left: number
  code_length: number
  resend_available_at: string | null
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
  on_file: boolean
}

export interface DocumentNumberRow {
  key: string
  label: string
  value: string | null
  editable: boolean
  error?: string | null
}

export interface DocumentUploadPayload {
  mode: 'intake' | 'reupload'
  requested_doc_types: string[]
  remarks: string | null
  docs: DraftDocumentRow[]
  numbers?: DocumentNumberRow[]
  required_uploaded: number
  required_total: number
  allowed_extensions: string[]
  max_mb: number
}

export interface CaseRequestRow {
  id: string
  kind: 'reupload' | 'contacts' | 'sales_data'
  label: string
  remarks: string
  doc_types: string[]
  requested_at: string
}

export interface CaseStatusPayload {
  reference: string
  status: string
  stage: 'submitted' | 'first_review' | 'second_review' | 'outcome'
  stage_label: string
  status_headline: string | null
  owner_role: string
  last_change: string
  open_requests: CaseRequestRow[]
  outcome: 'approved' | 'rejected' | null
  outcome_remarks: string | null
  next_step: string
}

export interface ContactRow {
  role: string
  label: string
  required: boolean
  first_name: string | null
  last_name: string | null
  email: string | null
  phone: string | null
  source: Source | null
  confirmed: boolean
  same_as_primary: boolean
}

export interface ContactsPayload {
  request_id: string | null
  remarks: string | null
  rows: ContactRow[]
  can_submit: boolean
  blockers: string[]
}

export interface SalesDataPayload {
  request_id: string | null
  remarks: string | null
  uploaded: boolean
  file_name: string | null
  size_bytes: number | null
  allowed_extensions: string[]
  max_mb: number
}

/** Reviewer console assistant — Use prefills action forms (never submits). */
export interface ReviewerSuggestionPayload {
  kind:
    | 'yardi_company'
    | 'yardi_brand'
    | 'reupload_remarks'
    | 'rejection_remarks'
    | 'contacts_request'
    | 'tenant_reminder'
  action:
    'request_reupload' | 'reject' | 'request_contacts' | 'relink_company' | 'relink_brand' | ''
  payload: Record<string, unknown>
  text: string
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
  | {
      card_id: string
      card_type: 'form_mode'
      message_id: string | null
      payload: FormModePayload
    }
  | {
      card_id: string
      card_type: 'handoff'
      message_id: string | null
      payload: HandoffPayload
    }
  | {
      card_id: string
      card_type: 'case_status'
      message_id: string | null
      payload: CaseStatusPayload
    }
  | {
      card_id: string
      card_type: 'contacts'
      message_id: string | null
      payload: ContactsPayload
    }
  | {
      card_id: string
      card_type: 'sales_data_upload'
      message_id: string | null
      payload: SalesDataPayload
    }
  | {
      card_id: string
      card_type: 'reviewer_suggestion'
      message_id: string | null
      payload: ReviewerSuggestionPayload
    }
  | {
      card_id: string
      card_type: 'basic_info_review'
      message_id: string | null
      payload: BasicInfoReviewPayload
    }
  | {
      card_id: string
      card_type: 'send_link'
      message_id: string | null
      payload: SendLinkPayload
    }
  | {
      card_id: string
      card_type: 'existing_cr_choice'
      message_id: string | null
      payload: ExistingCrChoicePayload
    }
  | {
      card_id: string
      card_type: 'sign_in_prompt'
      message_id: string | null
      payload: SignInPromptPayload
    }

export type FormModeStep =
  'existing_account' | 'cr' | 'details' | 'verification' | 'documents' | 'review' | 'submitted'

/** A value still missing in form mode; saved with the `edit_field` action. */
export interface FormModeField {
  /** A field key, or `contact_number` (saved as mobile or landline). */
  key: string
  label: string
  kind: 'text' | 'select'
  /** For selects: GET /api/master/{master_kind}. */
  master_kind: string | null
}

/** The model is unavailable: finish the inquiry from the cards (L3 §3.14). */
export interface FormModePayload {
  /** False once the assistant is back. */
  active: boolean
  message: string
  next_step: FormModeStep
  fields: FormModeField[]
  can_skip_cr: boolean
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
  follow_on_of: string | null
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

export interface TranscriptMessage {
  id: string
  role: 'assistant' | 'user'
  text: string
}

export interface CreateSessionResponse {
  session_id: string
  messages: TranscriptMessage[]
  cards: UiCard[]
  draft: DraftSummary
}

export interface VerifyEmailResponse {
  status: 'verified'
  session_id: string
  email_masked: string | null
  resume_token: string
}

export interface InquiryStatusStage {
  key: string
  label: string
  state: StepState
}

export interface InquiryStatusResponse {
  reference: string
  status: 'under_review' | 'approved' | 'sent_to_yardi' | 'rejected'
  summary: string
  submitted_at: string
  steps: InquiryStatusStage[]
  stages: InquiryStatusStage[]
  current_stage: string
  owner_role: string
  waiting_on_you: string[]
  last_change: string | null
}

export interface OutboxMessage {
  id: string
  inquiry_id: string
  channel: 'email' | 'sms'
  to: string
  template: string
  kind: string
  subject: string
  body: string
  links: string[]
  created_at: string
}
