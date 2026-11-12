"""Inquiry status for the tracking page (L3 §3.4, L4 §3.8).

From the case when the review lifecycle has one (Day 4), else from the submission. The
owner is a role, never a person. A case that passed first review is a **lead**
(requirements §7.1.1 b).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from app import clock
from app.services.errors import ReferenceNotFoundError
from app.services.submit import MockSubmitService
from app.workflow.labels import FORECASTED_SALES_DATA, STATUS_PAGE_STAGES, rejection_label
from app.workflow.models import ROLE_LABELS, Case, CaseStatus, review_level
from app.workflow.store import CaseStore

StatusValue = Literal["under_review", "approved", "sent_to_yardi", "rejected"]
StageKey = Literal["submitted", "first_review", "second_review", "outcome"]
StageState = Literal["done", "current", "upcoming"]

# Stage names from the v2 flowchart (flow v2 §3.5, `workflow/labels.py`).
_STAGE_KEYS: tuple[StageKey, ...] = ("submitted", "first_review", "second_review", "outcome")
STAGES: list[tuple[StageKey, str]] = [(key, STATUS_PAGE_STAGES[key]) for key in _STAGE_KEYS]

# A submission with no case yet: owner by product line (requirements §7.1.1 b; flow v2 §3.5).
OWNER_ROLES: dict[str, str] = {
    "store": ROLE_LABELS["rlm_store"],
    "office": ROLE_LABELS["rlm_store"],
    "media": ROLE_LABELS["rplm_media"],
    "specialty": ROLE_LABELS["rplm_specialty"],
}
DEFAULT_OWNER_ROLE = "Leasing team"


@dataclass(frozen=True)
class InquiryStatus:
    reference: str
    status: StatusValue
    submitted_at: datetime
    current_stage: StageKey = "first_review"
    owner_role: str = DEFAULT_OWNER_ROLE
    waiting_on_you: list[str] = field(default_factory=list)
    last_change: datetime | None = None
    # "Tenant Not Qualified" or "Lead Rejected" (flow v2 §3.5); None unless rejected.
    rejection_label: str | None = None


REQUEST_LABELS: dict[str, str] = {
    "reupload": "Re-upload documents",
    "contacts": "Add company contacts",
    "sales_data": f"Upload {FORECASTED_SALES_DATA.lower()}",
}

# Wording after final approval (L4 §3.8): only promise a proposal once Yardi has acknowledged.
FINAL_APPROVAL_LABELS: dict[Literal["approved", "sent_to_yardi"], str] = {
    "approved": "Approved — we're passing your details to the leasing team",
    "sent_to_yardi": "Approved — your details are with the leasing team for a proposal",
}


# The last stage once there is one: done, and named (re-demo flow 1, 10 Nov: it stayed
# "Outcome", marked in progress, after the case was approved).
OUTCOME_LABELS: dict[StatusValue, str] = {
    "approved": "Outcome — Approved",
    "sent_to_yardi": "Outcome — Approved",
    "rejected": "Outcome — Not approved",
}


def status_stages(inquiry: InquiryStatus) -> list[tuple[StageKey, str, StageState]]:
    """`(key, label, state)` per stage; a decided outcome is done and says what it was."""
    current = next(i for i, (key, _label) in enumerate(STAGES) if key == inquiry.current_stage)
    decided = inquiry.current_stage == "outcome" and inquiry.status in OUTCOME_LABELS
    stages: list[tuple[StageKey, str, StageState]] = []
    for i, (key, label) in enumerate(STAGES):
        if key == "outcome" and decided:
            outcome = OUTCOME_LABELS[inquiry.status]
            if inquiry.status == "rejected" and inquiry.rejection_label:
                outcome = f"Outcome — {inquiry.rejection_label}"
            stages.append((key, outcome, "done"))
            continue
        state: StageState = "done" if i < current else "current" if i == current else "upcoming"
        stages.append((key, label, state))
    return stages


def final_approval_label(status: StatusValue) -> str | None:
    if status in FINAL_APPROVAL_LABELS:
        return FINAL_APPROVAL_LABELS[status]
    return None


def inquiry_status_summary(inquiry: InquiryStatus) -> str:
    if label := final_approval_label(inquiry.status):
        return label
    if inquiry.status == "rejected":
        if inquiry.rejection_label:
            return f"Your inquiry was not approved ({inquiry.rejection_label})."
        return "Your inquiry was not approved."
    owner = f" Current owner: {inquiry.owner_role}." if inquiry.owner_role else ""
    return f"Your inquiry was submitted and is waiting for review.{owner}"


def _from_case(case: Case) -> InquiryStatus:
    stage: StageKey
    status: StatusValue = "under_review"
    if case.status in (CaseStatus.SUBMITTED,):
        stage = "submitted"
    elif case.status in (CaseStatus.FIRST_REVIEW, CaseStatus.REUPLOAD_REQUESTED):
        stage = "first_review"
    elif case.status == CaseStatus.SECOND_REVIEW:
        stage = "second_review"
    else:
        stage = "outcome"
        if case.status == CaseStatus.REJECTED:
            status = "rejected"
        elif case.status == CaseStatus.SENT_TO_YARDI:
            status = "sent_to_yardi"
        else:
            status = "approved"  # approved, not yet acknowledged by Yardi
    queue = case.review_queue
    owner = (
        ROLE_LABELS.get(queue.role_for(review_level(case.status)), DEFAULT_OWNER_ROLE)
        if queue
        else DEFAULT_OWNER_ROLE
    )
    waiting = [REQUEST_LABELS[r.kind] for r in case.requests if r.status == "open"]
    return InquiryStatus(
        reference=case.reference,
        status=status,
        submitted_at=case.submitted_at,
        current_stage=stage,
        owner_role=owner,
        waiting_on_you=waiting,
        last_change=case.last_change,
        rejection_label=rejection_label(case),
    )


class StatusService(Protocol):
    def get(self, reference: str) -> InquiryStatus: ...


class MockStatusService:
    def __init__(self, submit_service: MockSubmitService, cases: CaseStore | None = None) -> None:
        self._submit_service = submit_service
        self._cases = cases

    def get(self, reference: str) -> InquiryStatus:
        case = self._cases.get(reference) if self._cases else None
        if case is not None:
            return _from_case(case)
        payload = self._submit_service.submissions.get(reference)
        if payload is None:
            raise ReferenceNotFoundError(f"Unknown reference: {reference}")
        submitted_raw = payload.get("submitted_at")
        if isinstance(submitted_raw, str):
            submitted_at = datetime.fromisoformat(submitted_raw)
        else:
            submitted_at = clock.now()
        unit_type = ((payload.get("fields") or {}).get("unit_type") or {}).get("value")
        return InquiryStatus(
            reference=reference,
            status="under_review",
            submitted_at=submitted_at,
            current_stage="first_review",
            owner_role=OWNER_ROLES.get(str(unit_type), DEFAULT_OWNER_ROLE),
            waiting_on_you=[],
            last_change=submitted_at,
        )
