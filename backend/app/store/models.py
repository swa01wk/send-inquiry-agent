"""Durable inquiry model (M0 §5.1) and session-scoped UI state."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models import InquiryDraft


class InquiryStatus(StrEnum):
    DRAFT = "draft"
    # Flow v2 (§3.3, FV12): verified, not submitted; abandoned after the pending TTL.
    PENDING = "pending"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ABANDONED = "abandoned"
    REDIRECTED = "redirected"
    FIRST_REVIEW = "first_review"
    REUPLOAD_REQUESTED = "reupload_requested"
    SECOND_REVIEW = "second_review"
    LEAD_APPROVED = "lead_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_TO_YARDI = "sent_to_yardi"


class SessionState(BaseModel):
    """Fields stored in `session_state` jsonb (not first-class columns)."""

    confirm_card_turns: dict[str, int] = Field(default_factory=dict)
    turn_index: int = 0
    transcript: list[dict[str, str]] = Field(default_factory=list)
    cards: dict[str, dict[str, Any]] = Field(default_factory=dict)
    inquiry_seq: int = 1
    form_mode: bool = False
    mode: str = "intake"
    contacts_draft: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str | None = None
    link_sent_to: str | None = None
    complete_nonce: str | None = None
    closed: str | None = None
    contact_check: str | None = None
    contact_email: str | None = None
    origin_id: str | None = None
    signatory_answer: str | None = None
    test_scenario: str | None = None
    script_step: int = 0


class Inquiry(BaseModel):
    id: UUID
    status: InquiryStatus = InquiryStatus.DRAFT
    draft: InquiryDraft
    cards_shown: list[str] = Field(default_factory=list)
    confirm_card_keys: dict[str, list[str]] = Field(default_factory=dict)
    card_counter: int = 0
    submit_key: str | None = None
    reference: str | None = None
    version: int = 0
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    channel: str = "self_service"
    case_id: str | None = None
    tenant_id: str | None = None
    staff_id: str | None = None
    session_state: SessionState = Field(default_factory=SessionState)

    def cards_shown_set(self) -> set[str]:
        return set(self.cards_shown)

    def set_cards_shown(self, value: set[str] | list[str]) -> None:
        self.cards_shown = sorted(value)


def settle_status(inquiry: Inquiry) -> None:
    """The status a save implies: submitted once the draft has a reference; `pending` once a
    flow v2 public inquiry is verified (FV12)."""
    draft = inquiry.draft
    if inquiry.status in (InquiryStatus.DRAFT, InquiryStatus.PENDING) and draft.reference:
        inquiry.status = InquiryStatus.SUBMITTED
    elif (
        inquiry.status == InquiryStatus.DRAFT
        and inquiry.case_id is None
        and draft.intake_flow == "v2"
        and draft.verified_at is not None
        and draft.cr_status != "existing"
    ):
        inquiry.status = InquiryStatus.PENDING


def owned_reference(inquiry: Inquiry) -> str | None:
    """The reference this row records in the unique `reference` column.

    Only the intake inquiry owns its reference. A case-chat row (`case_id` set, opened from a
    case or tracking link) is seeded with a copy of the submitted draft, reference included;
    it must not claim the same reference, or the second row breaks the unique constraint.
    """
    if inquiry.reference:
        return inquiry.reference
    if inquiry.case_id:
        return None
    return inquiry.draft.reference
