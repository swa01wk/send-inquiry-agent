"""Case data: what an inquiry carries after submission (L4 §3.1).

Written only by the state machine (`machine.transition`), its effects, or deterministic
UI actions; never by the LLM. A case is keyed by its reference.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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


ReviewRole = Literal["lease_admin", "rlm_store", "rplm_media", "rplm_specialty"]
ReviewLevel = Literal["first", "final"]
RequestKind = Literal["reupload", "contacts", "sales_data"]
# A reviewer's decision on one document or one contact (demo feedback §3.4, §3.5).
ApprovalStatus = Literal["pending", "approved", "rejected"]
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
# Display names from the v2 flowchart (flow v2 §3.5, M17): the ids don't change; RLM-Store
# was renamed Regional Sales Manager (same queue and people).
ROLE_LABELS: dict[str, str] = {
    "lease_admin": "Leasing Admin",
    "rlm_store": "Regional Sales Manager",
    "rplm_media": "Regional Product Line Manager (Media)",
    "rplm_specialty": "Regional Product Line Manager (Specialty)",
}


# Statuses in which the first review level is acting (demo feedback §3.2).
FIRST_LEVEL_STATES: frozenset[CaseStatus] = frozenset(
    {CaseStatus.FIRST_REVIEW, CaseStatus.REUPLOAD_REQUESTED}
)


def review_level(status: CaseStatus) -> ReviewLevel:
    """The review level a case is with: first (and its re-upload loop) or final."""
    return "first" if status in FIRST_LEVEL_STATES else "final"


class ReviewQueue(BaseModel):
    product_line: Literal["store", "media", "specialty"]
    region: str
    role: ReviewRole  # the final reviewer for the product line (policy `review_routing`)
    # First-level reviewer (demo feedback §3.2, policy `first_level_review_role`). None:
    # the final reviewer does both levels (cases routed before 5 Nov 2026).
    first_role: ReviewRole | None = None

    def role_for(self, level: ReviewLevel) -> ReviewRole:
        """The role that acts at this review level."""
        if level == "first" and self.first_role is not None:
            return self.first_role
        return self.role

    @property
    def roles(self) -> tuple[ReviewRole, ...]:
        """Every role that works this queue (both levels)."""
        return tuple(dict.fromkeys((self.role_for("first"), self.role)))


class CaseRequest(BaseModel):
    id: str
    kind: RequestKind
    status: Literal["open", "fulfilled", "withdrawn"] = "open"
    doc_types: list[DocType] = Field(default_factory=list)
    # Contacts requests opened by a rejected contact: only these roles (demo feedback §3.5).
    roles: list[ContactRole] = Field(default_factory=list)
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


class DocumentDecision(BaseModel):
    """The first-level reviewer's decision on one upload (demo feedback §3.4, ADR-R4): it
    names the `file_id` it was made on, and a replaced file starts a new pending decision."""

    doc_type: DocType
    file_id: str
    status: ApprovalStatus = "pending"
    remarks: str | None = None
    # The document review service's answer for this upload (`pending`: it didn't answer).
    review_status: Literal["done", "pending", "failed"] | None = None
    expiry_extracted: date | None = None  # from the document review service
    expiry_confirmed: date | None = None  # entered or corrected by the reviewer
    expiry_confirmed_by: str | None = None
    by: str | None = None
    at: datetime | None = None

    @property
    def expiry(self) -> date | None:
        """The date in force: the reviewer's, else the review service's."""
        return self.expiry_confirmed or self.expiry_extracted

    @classmethod
    def for_upload(cls, ref: DocumentRef) -> DocumentDecision:
        review = ref.review
        return cls(
            doc_type=ref.doc_type,
            file_id=ref.file_id,
            review_status=review.status if review else None,
            expiry_extracted=review.expiry_date if review else None,
        )


CONTACT_VALUE_FIELDS = ("first_name", "last_name", "email", "mobile", "landline")


class TenantContact(BaseModel):
    role: ContactRole
    first_name: FieldValue = Field(default_factory=FieldValue)
    last_name: FieldValue = Field(default_factory=FieldValue)
    email: FieldValue = Field(default_factory=FieldValue)
    mobile: FieldValue = Field(default_factory=FieldValue)
    landline: FieldValue = Field(default_factory=FieldValue)
    same_as_primary: bool = False
    # Contact approval (demo feedback §3.5). Set by the state machine only: whatever the
    # applicant's payload says here is ignored. A changed contact gets a new id, so an
    # approval made on the old values can't land on the new ones (ADR-R4).
    contact_id: str = ""
    approval: ApprovalStatus = "pending"
    approval_remarks: str | None = None
    approved_by: str | None = None  # a reviewer id, or "system:<reason>"
    added_by: Literal["tenant", "reviewer", "system"] = "tenant"

    @model_validator(mode="after")
    def _stable_id(self) -> TenantContact:
        # Contacts saved before 5 Nov 2026 have no id: one per role is stable across loads.
        if not self.contact_id:
            self.contact_id = f"ct_{self.role}"
        return self

    def values(self) -> tuple[Any, ...]:
        """What the contact says (not where it came from): compared to detect a change."""
        return (
            *(getattr(self, name).value for name in CONTACT_VALUE_FIELDS),
            self.same_as_primary,
        )


class Invitation(BaseModel):
    id: str
    email: str
    role: str  # the tenant role the invitation assigns
    invited_at: datetime
    accepted_at: datetime | None = None
    # Reject Lead revoked it (flow v2 §3.6, V9).
    revoked_at: datetime | None = None


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
    # One per intake document on the case (demo feedback §3.4); see `workflow.documents`.
    document_decisions: dict[DocType, DocumentDecision] = Field(default_factory=dict)
    sales_data: DocumentRef | None = None
    document_history: list[DocumentRef] = Field(default_factory=list)
    onboarding: Onboarding = Field(default_factory=Onboarding)
    yardi: YardiLink = Field(default_factory=YardiLink)
    events: list[CaseEvent] = Field(default_factory=list)
    effects_done: list[str] = Field(default_factory=list)
    case_session_id: str | None = None  # the chat that answers requests (case mode)
    # Intake channel (intake channels §3.8): self_service | assisted | existing_tenant.
    channel: str = "self_service"
    created_by: str | None = None  # a staff id or tenant id; None = the applicant
    tenant_id: str | None = None

    @property
    def event_seq(self) -> int:
        return len(self.events)

    def open_request(self, kind: RequestKind) -> CaseRequest | None:
        return next((r for r in self.requests if r.kind == kind and r.status == "open"), None)

    def request_by_id(self, request_id: str) -> CaseRequest | None:
        return next((r for r in self.requests if r.id == request_id), None)

    def contact_by_id(self, contact_id: str) -> TenantContact | None:
        return next((c for c in self.tenant_contacts if c.contact_id == contact_id), None)

    @property
    def last_change(self) -> datetime:
        return self.events[-1].at if self.events else self.submitted_at


class WorkflowEvent(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
