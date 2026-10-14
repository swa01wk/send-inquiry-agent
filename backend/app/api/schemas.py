"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.summary import DraftChecks, DraftDocumentRow, DraftSummary

CardType = Literal[
    "confirm_fields",
    "mall_picker",
    "otp_input",
    "document_upload",
    "review",
    "success",
    "quick_replies",
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
    role: Literal["assistant"] = "assistant"
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


class OtpSentTo(BaseModel):
    mobile_masked: str | None
    email_masked: str | None


class OtpInputPayload(BaseModel):
    sent_to: OtpSentTo
    attempts_left: int
    verified: bool
    code_length: int = 4


class DocumentUploadPayload(BaseModel):
    docs: list[DraftDocumentRow]
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


class ChatRequestMessage(BaseModel):
    type: Literal["message"]
    text: str


class ChatRequestAction(BaseModel):
    type: Literal["action"]
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


ChatRequest = ChatRequestMessage | ChatRequestAction
