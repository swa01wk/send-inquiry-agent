"""Inquiry status (simulated Tenant Admin Platform status, L3 §3.4).

Until the review lifecycle exists (Day 4), every submitted inquiry is waiting for
first-level review. The owner is a role, never a person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.services.errors import ReferenceNotFoundError
from app.services.submit import MockSubmitService

StatusValue = Literal["under_review"]
StageKey = Literal["submitted", "first_review", "second_review", "outcome"]

STAGES: list[tuple[StageKey, str]] = [
    ("submitted", "Inquiry submitted"),
    ("first_review", "First review"),
    ("second_review", "Second review"),
    ("outcome", "Outcome"),
]

# Requirements §7.1.1 b: first-level reviewers by product line.
OWNER_ROLES: dict[str, str] = {
    "store": "Regional Leasing Manager (Store)",
    "media": "Regional Property Leasing Manager (Media)",
    "specialty": "Regional Property Leasing Manager (Specialty)",
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


class StatusService(Protocol):
    def get(self, reference: str) -> InquiryStatus: ...


class MockStatusService:
    def __init__(self, submit_service: MockSubmitService) -> None:
        self._submit_service = submit_service

    def get(self, reference: str) -> InquiryStatus:
        payload = self._submit_service.submissions.get(reference)
        if payload is None:
            raise ReferenceNotFoundError(f"Unknown reference: {reference}")
        submitted_raw = payload.get("submitted_at")
        if isinstance(submitted_raw, str):
            submitted_at = datetime.fromisoformat(submitted_raw)
        else:
            submitted_at = datetime.now(tz=UTC)
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
