"""Case data: what an inquiry carries after submission (L4 §3.1).

Written only by the state machine (`machine.transition`), its effects, or deterministic
UI actions; never by the LLM. A case is keyed by its reference.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.models import DocType, DocumentRef, FieldValue, InquiryDraft


class CaseStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    FIRST_REVIEW = "first_review"
    REUPLOAD_REQUESTED = "reupload_requested"
    SECOND_REVIEW = "second_review"
    APPROVED = "approved"
    SENT_TO_YARDI = "sent_to_yardi"
    REJECTED = "rejected"
    ABANDONED = "abandoned"
    REDIRECTED = "redirected"


ReviewRole = Literal["rlm_store", "rplm_media", "rplm_specialty"]
RequestKind = Literal["reupload", "contacts", "sales_data"]
ContactRole = Literal[
    "authorized_signatory",
    "billing_contact",
    "leasing_manager",
    "financial_controller",
    "company_admin",
]
CONTACT_ROLE_LABELS: dict[str, str] = {
    "authorized_signatory": "Authorized Signatory",
    "billing_contact": "Billing Contact",
    "leasing_manager": "Leasing Manager",
    "financial_controller": "Financial Controller",
    "company_admin": "Company Admin",
}
ROLE_LABELS: dict[str, str] = {
    "rlm_store": "Regional Leasing Manager (Store)",
    "rplm_media": "Regional Property Leasing Manager (Media)",
    "rplm_specialty": "Regional Property Leasing Manager (Specialty)",
}


class ReviewQueue(BaseModel):
    product_line: Literal["store", "media", "specialty"]
    region: str
    role: ReviewRole


class CaseRequest(BaseModel):
    id: str
    kind: RequestKind
    status: Literal["open", "fulfilled", "withdrawn"] = "open"
    doc_types: list[DocType] = Field(default_factory=list)
    remarks: str = ""
    requested_by: str
    requested_at: datetime
    closed_at: datetime | None = None


class Decision(BaseModel):
    level: Literal["first", "second"]
    outcome: Literal["approved", "rejected"]
    remarks: str | None = None
    reason_category: str | None = None
    by: str
    at: datetime


class TenantContact(BaseModel):
    role: ContactRole
    first_name: FieldValue = Field(default_factory=FieldValue)
    last_name: FieldValue = Field(default_factory=FieldValue)
    email: FieldValue = Field(default_factory=FieldValue)
    mobile: FieldValue = Field(default_factory=FieldValue)
    landline: FieldValue = Field(default_factory=FieldValue)
    same_as_primary: bool = False


class Invitation(BaseModel):
    id: str
    email: str
    role: str  # the tenant role the invitation assigns
    invited_at: datetime
    accepted_at: datetime | None = None


class Onboarding(BaseModel):
    invitations: list[Invitation] = Field(default_factory=list)


class YardiLink(BaseModel):
    company_id: str | None = None
    brand_id: str | None = None
    lead_ref: str | None = None
    sent_at: datetime | None = None
    attempts: int = 0
    needs_operations: bool = False  # Yardi kept failing: flagged in the console


class CaseEvent(BaseModel):
    """One applied transition (kept on the case for stage ages; the audit log has all)."""

    seq: int
    name: str
    from_status: CaseStatus
    to_status: CaseStatus
    actor: str  # "user" | "system" | "reviewer:<id>" | "staff:<id>"
    at: datetime


class Case(BaseModel):
    id: str  # the reference
    reference: str
    session_id: str  # the chat the inquiry was raised in
    inquiry_seq: int = 1
    status: CaseStatus = CaseStatus.SUBMITTED
    draft: InquiryDraft  # the inquiry as submitted; documents updated by re-uploads
    submitted_at: datetime
    review_queue: ReviewQueue | None = None
    requests: list[CaseRequest] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    tenant_contacts: list[TenantContact] = Field(default_factory=list)
    sales_data: DocumentRef | None = None
    document_history: list[DocumentRef] = Field(default_factory=list)
    onboarding: Onboarding = Field(default_factory=Onboarding)
    yardi: YardiLink = Field(default_factory=YardiLink)
    events: list[CaseEvent] = Field(default_factory=list)
    effects_done: list[str] = Field(default_factory=list)
    case_session_id: str | None = None  # the chat that answers requests (case mode)

    @property
    def event_seq(self) -> int:
        return len(self.events)

    def open_request(self, kind: RequestKind) -> CaseRequest | None:
        return next((r for r in self.requests if r.kind == kind and r.status == "open"), None)

    def request_by_id(self, request_id: str) -> CaseRequest | None:
        return next((r for r in self.requests if r.id == request_id), None)

    @property
    def last_change(self) -> datetime:
        return self.events[-1].at if self.events else self.submitted_at


class WorkflowEvent(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
