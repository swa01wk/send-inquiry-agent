"""Wording after final approval (Day 5 A3)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.case_cards import build_case_status_card
from app.domain.draft_ops import new_inquiry_draft
from app.services.status import (
    FINAL_APPROVAL_LABELS,
    InquiryStatus,
    final_approval_label,
    inquiry_status_summary,
)
from app.workflow.models import Case, CaseStatus

T0 = datetime(2026, 10, 30, 9, tzinfo=UTC)


def test_final_approval_labels():
    assert final_approval_label("approved") == FINAL_APPROVAL_LABELS["approved"]
    assert final_approval_label("sent_to_yardi") == FINAL_APPROVAL_LABELS["sent_to_yardi"]
    assert final_approval_label("under_review") is None


def test_inquiry_status_summary_uses_final_approval_copy():
    approved = InquiryStatus(
        reference="GEO-STR-000001",
        status="approved",
        submitted_at=T0,
        current_stage="outcome",
    )
    assert inquiry_status_summary(approved) == FINAL_APPROVAL_LABELS["approved"]

    sent = InquiryStatus(
        reference="GEO-STR-000002",
        status="sent_to_yardi",
        submitted_at=T0,
        current_stage="outcome",
    )
    assert inquiry_status_summary(sent) == FINAL_APPROVAL_LABELS["sent_to_yardi"]


def test_case_status_card_exposes_status_headline():
    draft = new_inquiry_draft()
    for workflow_status, api_status in (
        (CaseStatus.APPROVED, "approved"),
        (CaseStatus.SENT_TO_YARDI, "sent_to_yardi"),
    ):
        case = Case(
            id="GEO-STR-000099",
            reference="GEO-STR-000099",
            session_id="s1",
            status=workflow_status,
            draft=draft,
            submitted_at=T0,
            last_change=T0,
        )
        card = build_case_status_card(case)
        assert card.payload["status"] == api_status
        assert card.payload["status_headline"] == FINAL_APPROVAL_LABELS[api_status]  # type: ignore[index]
