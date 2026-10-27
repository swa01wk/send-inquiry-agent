"""Audit log v0 (M0 §8 at Day 2 depth): append-only events per inquiry, redacted at write.

`AuditLog.record(inquiry_id, type, actor, payload)` keeps only the payload keys allowed
for that event type (`ALLOWED_KEYS`), and never keeps codes, tokens, raw contact details,
file names or message text. Events live in memory and, when `DATA_DIR` is set, in
`<DATA_DIR>/audit/<inquiry_id>.json` so they survive a restart.

The `inquiry_events` table, correlation ids and `audit_dump.py` arrive in step 15.
"""

from __future__ import annotations

import hashlib
import re
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from app.persistence import JsonFile, data_path

Actor = Literal["user", "agent", "system", "reviewer", "staff"]

# Payload keys each event type may keep. Anything else is dropped.
ALLOWED_KEYS: dict[str, frozenset[str]] = {
    "inquiry_created": frozenset({"channel"}),
    "user_message": frozenset({"chars", "message_id"}),
    "ui_action": frozenset({"action", "outcome"}),
    "tool_called": frozenset({"layer", "name", "outcome", "latency_ms"}),
    "field_written": frozenset(
        {"key", "source", "confirmed", "value_sha256", "display", "evidence"}
    ),
    "field_confirmed": frozenset({"keys", "via"}),
    "guard_verdict": frozenset({"rule", "retried", "retractions"}),
    "card_shown": frozenset({"card_type", "card_id"}),
    "verification_sent": frozenset({"channel", "result"}),
    "verification_result": frozenset({"channel", "result"}),
    "document_added": frozenset({"doc_type", "ext", "size_bytes"}),
    "document_removed": frozenset({"doc_type"}),
    "submit_attempt": frozenset({"submit_key", "outcome"}),
    "submit_result": frozenset({"submit_key", "outcome", "reference", "repeat"}),
    "notification_sent": frozenset({"template", "channel", "outcome", "message_id"}),
    "error": frozenset({"where", "kind"}),
    "handoff_created": frozenset({"reason", "case_id", "created", "via"}),
    "follow_on_started": frozenset({"from_reference", "inquiry_seq", "reused_verification"}),
    "form_mode_entered": frozenset({"kind"}),
    "form_mode_left": frozenset(),
}

# Never kept, whatever the event type says.
FORBIDDEN_KEYS = frozenset(
    {"code", "token", "email", "mobile", "landline", "file_name", "to", "text", "value", "body"}
)

# Personal fields: a hash instead of the value in `field_written`.
HASHED_FIELDS = frozenset(
    {"first_name", "last_name", "email", "mobile", "landline", "national_id_number"}
)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_DIGITS_RE = re.compile(r"\+?\d[\d\s-]{6,}\d")


def value_hash(value: Any) -> str:
    return hashlib.sha256(str(value).strip().lower().encode("utf-8")).hexdigest()[:16]


def _clean(value: Any) -> Any:
    """Scrub stray emails and long digit runs from any string that slips into a payload."""
    if isinstance(value, str):
        return _LONG_DIGITS_RE.sub("[number]", _EMAIL_RE.sub("[email]", value))
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def redact(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = ALLOWED_KEYS[event_type]
    kept: dict[str, Any] = {}
    for key, value in payload.items():
        if key in FORBIDDEN_KEYS or key not in allowed:
            continue
        kept[key] = _clean(value)
    return kept


class AuditLog:
    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = data_dir
        self._events: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def _file(self, inquiry_id: str) -> JsonFile:
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", inquiry_id)
        return JsonFile(data_path(self._data_dir, "audit", f"{safe}.json"))

    def _load(self, inquiry_id: str) -> list[dict[str, Any]]:
        if inquiry_id not in self._events:
            self._events[inquiry_id] = list(self._file(inquiry_id).load([]))
        return self._events[inquiry_id]

    def record(
        self,
        inquiry_id: str,
        event_type: str,
        *,
        actor: Actor,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if event_type not in ALLOWED_KEYS:
            msg = f"unknown audit event type: {event_type}"
            raise ValueError(msg)
        with self._lock:
            events = self._load(inquiry_id)
            events.append(
                {
                    "seq": len(events) + 1,
                    "at": datetime.now(tz=UTC).isoformat(),
                    "type": event_type,
                    "actor": actor,
                    "payload": redact(event_type, payload or {}),
                }
            )
            self._file(inquiry_id).save(events)

    def events(self, inquiry_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(e) for e in self._load(inquiry_id)]
