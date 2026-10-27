"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.summary import DraftChecks, DraftDocumentRow, DraftSummary

CardType = Literal[
    "confirm_fields",
    "mall_picker",
    "verification",
    "document_upload",
    "review",
    "success",
    "quick_replies",
    "handoff",
    "form_mode",
]

StepState = Literal["done", "current", "upcoming"]
SuccessStepState = Literal["done", "current", "upcoming"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AssistantMessage(BaseModel):
    id: str
    # "user" appears only when a chat is resumed (POST /api/sessions/resume).
    role: Literal["assistant", "user"] = "assistant"
    text: str


class UiCard(BaseModel):
    card_id: str
    card_type: CardType
    message_id: str | None = None
    payload: dict[str, Any]


class ConfirmFieldRow(BaseModel):
    key: str
    label: str
    display: str | None
    source: str | None
    confirmed: bool
    # Derived values: the user's words the value came from ("from: '…'", L3 §3.9).
    evidence: str | None = None


class ConfirmFieldsPayload(BaseModel):
    title: str
    fields: list[ConfirmFieldRow]
    all_confirmed: bool


class MallPickerCity(BaseModel):
    id: str
    label: str


class MallPickerMall(BaseModel):
    id: str
    name: str


class MallPickerPayload(BaseModel):
    city: MallPickerCity
    malls: list[MallPickerMall]
    selected: list[str]
    min_select: int = 1
    # One mall per inquiry: the picker behaves as a single choice.
    max_select: int = 1


class VerificationEmail(BaseModel):
    masked: str | None
    link_sent: bool
    verified: bool
    # Demo only (EMAIL_LINK_DEMO): stands in for clicking the emailed link.
    demo_token: str | None = None
    # ISO time when Resend is allowed again (cooldown / hourly cap); None = now.
    resend_available_at: str | None = None


class VerificationMobile(BaseModel):
    masked: str | None
    code_sent: bool
    verified: bool
    attempts_left: int
    code_length: int = 4
    resend_available_at: str | None = None


class VerificationPayload(BaseModel):
    email: VerificationEmail
    # None when the applicant gave only a landline: email alone verifies them.
    mobile: VerificationMobile | None
    all_verified: bool


class DocumentNumberRow(BaseModel):
    key: str
    label: str
    value: str | None
    editable: bool
    error: str | None = None


class DocumentUploadPayload(BaseModel):
    docs: list[DraftDocumentRow]
    numbers: list[DocumentNumberRow] = Field(default_factory=list)
    required_uploaded: int
    required_total: int
    allowed_extensions: list[str]
    max_mb: int


class ReviewGroupRow(BaseModel):
    key: str
    label: str
    display: str | None
    source: str | None
    confirmed: bool
    required: bool


class ReviewGroup(BaseModel):
    title: str
    rows: list[ReviewGroupRow]


class ReviewPayload(BaseModel):
    groups: list[ReviewGroup]
    documents: list[DraftDocumentRow]
    checks: DraftChecks
    can_submit: bool
    terms_accepted: bool
    blockers: list[str]


class SuccessStep(BaseModel):
    label: str
    detail: str
    state: SuccessStepState


class SuccessPayload(BaseModel):
    reference: str
    tracking_url: str
    steps: list[SuccessStep]


class HandoffPayload(BaseModel):
    """A person is reachable (L3 §3.6): the call centre's details and the inquiry's ref."""

    phone: str
    email: str
    hours: str
    short_ref: str
    case_id: str
    reason: str


FormModeStep = Literal[
    "existing_account", "cr", "details", "verification", "documents", "review", "submitted"
]


class FormModeField(BaseModel):
    """A value still missing, typed by the user (saved with the `edit_field` action)."""

    key: str  # a field key, or "contact_number" (saved as mobile or landline)
    label: str
    kind: Literal["text", "select"]
    master_kind: str | None = None  # for selects: GET /api/master/{master_kind}


class FormModePayload(BaseModel):
    """The model is unavailable: finish the inquiry from the cards (L3 §3.14)."""

    active: bool  # false once the assistant is back
    message: str
    next_step: FormModeStep
    fields: list[FormModeField] = Field(default_factory=list)
    can_skip_cr: bool = False


class QuickReplyOption(BaseModel):
    label: str
    text: str
    action: Literal["send", "focus_input"] = "send"
    placeholder: str | None = None


class QuickRepliesPayload(BaseModel):
    options: list[QuickReplyOption]


class CreateSessionResponse(BaseModel):
    session_id: str
    messages: list[AssistantMessage]
    cards: list[UiCard]
    draft: DraftSummary


class DocumentResponse(BaseModel):
    doc_type: str
    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    card: UiCard
    draft: DraftSummary


class DeleteDocumentResponse(BaseModel):
    card: UiCard
    draft: DraftSummary


class MasterItemResponse(BaseModel):
    id: str
    label: str


class UnitTypeResponse(MasterItemResponse):
    code: str


class MallResponse(BaseModel):
    id: str
    name: str
    city: str


class InquiryStatusStep(BaseModel):
    key: str
    label: str
    state: StepState


class InquiryStatusResponse(BaseModel):
    reference: str
    status: Literal["under_review"]
    submitted_at: datetime
    steps: list[InquiryStatusStep]
    # Day 2 (L3 §3.4): the stages, who holds the inquiry (a role), what waits on the applicant.
    stages: list[InquiryStatusStep] = Field(default_factory=list)
    current_stage: str = "first_review"
    owner_role: str = ""
    waiting_on_you: list[str] = Field(default_factory=list)
    last_change: datetime | None = None


class ResumeRequest(BaseModel):
    token: str


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    status: Literal["verified"]
    session_id: str
    email_masked: str | None
    # Signed `resume` token: POST /api/sessions/resume continues the chat on any device.
    resume_token: str


class ChatRequestMessage(BaseModel):
    type: Literal["message"]
    text: str


class ChatRequestAction(BaseModel):
    type: Literal["action"]
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


ChatRequest = ChatRequestMessage | ChatRequestAction
