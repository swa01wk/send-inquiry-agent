"""Call-centre cases for human handoff (L3 §3.6; requirements §7.1.1 a2).

`create_case` opens a case a customer-care executive picks up in the Tenant Admin
Platform, so they continue the same inquiry rather than starting over. In the POC the
mock keeps cases in `mock_world/cases.json` (with `DATA_DIR`) and emails each one to the
call-centre address, so it shows in the dev inbox.

One open case per inquiry: asking again shows the same case.
"""

from __future__ import annotations

import functools
import random
import threading
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

from app import clock
from app.notifications import MockNotificationService
from app.persistence import JsonFile, data_path

HandoffReason = Literal[
    "user_asked",
    "model_unavailable",
    "guard_retry",
    "gateway_failures",
    "submit_stuck",
    "repeated_correction",
]
HANDOFF_REASONS: tuple[str, ...] = (
    "user_asked",
    "model_unavailable",
    "guard_retry",
    "gateway_failures",
    "submit_stuck",
    "repeated_correction",
)
REASON_LABELS: dict[str, str] = {
    "user_asked": "The applicant asked to speak to someone",
    "model_unavailable": "The assistant was unavailable; the applicant asked for a call",
    "guard_retry": "The assistant couldn't give a safe answer twice in one turn",
    "gateway_failures": "A Cenomi system failed three times on the same step",
    "submit_stuck": "Submit couldn't be confirmed",
    "repeated_correction": "The applicant said something was wrong twice",
}


@dataclass(frozen=True)
class CallCentreCase:
    case_id: str
    inquiry_id: str
    reason: str
    short_ref: str
    summary: str
    status: Literal["open", "closed"]
    created_at: str
    payload: dict[str, Any]


class CallCentreService(Protocol):
    async def create_case(
        self,
        inquiry_id: str,
        payload: dict[str, Any],
        reason: str,
        transcript_summary: str,
        *,
        short_ref: str,
        context: dict[str, str],
    ) -> tuple[CallCentreCase, bool]: ...

    def open_case(self, inquiry_id: str) -> CallCentreCase | None: ...


class MockCallCentreService:
    def __init__(
        self,
        *,
        notifications: MockNotificationService,
        inbox_email: str,
        data_dir: str | None = None,
    ) -> None:
        self._notifications = notifications
        self._inbox = inbox_email
        self._file = JsonFile(data_path(data_dir, "mock_world", "cases.json"))
        self._cases: dict[str, dict[str, Any]] = dict(self._file.load({}))
        self._lock = threading.Lock()

    def open_case(self, inquiry_id: str) -> CallCentreCase | None:
        with self._lock:
            for raw in self._cases.values():
                if raw["inquiry_id"] == inquiry_id and raw["status"] == "open":
                    return CallCentreCase(**raw)
        return None

    def cases(self) -> list[CallCentreCase]:
        with self._lock:
            return [CallCentreCase(**raw) for raw in self._cases.values()]

    async def create_case(
        self,
        inquiry_id: str,
        payload: dict[str, Any],
        reason: str,
        transcript_summary: str,
        *,
        short_ref: str,
        context: dict[str, str],
    ) -> tuple[CallCentreCase, bool]:
        """The inquiry's open case, or a new one. Returns (case, created)."""
        existing = self.open_case(inquiry_id)
        if existing is not None:
            return existing, False
        with self._lock:
            case_id = f"CC-{random.randint(0, 999_999):06d}"
            while case_id in self._cases:
                case_id = f"CC-{random.randint(0, 999_999):06d}"
            case = CallCentreCase(
                case_id=case_id,
                inquiry_id=inquiry_id,
                reason=reason,
                short_ref=short_ref,
                summary=transcript_summary,
                status="open",
                created_at=clock.now().isoformat(),
                payload=payload,
            )
            self._cases[case_id] = asdict(case)
            self._file.save(self._cases)
        send = functools.partial(self._notifications.send, inquiry_id=inquiry_id)
        await send(
            "call_centre_case",
            self._inbox,
            {
                **context,
                "case_id": case_id,
                "short_ref": short_ref,
                "reason_label": REASON_LABELS.get(reason, reason),
                "summary": transcript_summary,
            },
        )
        return case, True
