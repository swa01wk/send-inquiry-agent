"""Inquiry status lookup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.services.errors import ReferenceNotFoundError
from app.services.submit import MockSubmitService

StatusValue = Literal["under_review"]


@dataclass(frozen=True)
class InquiryStatus:
    reference: str
    status: StatusValue
    submitted_at: datetime


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
        return InquiryStatus(
            reference=reference,
            status="under_review",
            submitted_at=submitted_at,
        )
