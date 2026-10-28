"""Notifications (L3 §3.4): templates rendered and delivered to the outbox.

Every message the system sends has a template in `templates/`, named by its trigger, with
a header (`kind`, `channel`, `subject`) and a `string.Template` body. In the POC,
`MockNotificationService` delivers to an outbox that the dev inbox (`/dev/inbox`,
`GET /api/dev/outbox`) shows. The outbox may hold the mock OTP; it is never logged.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any, Literal, Protocol

from app.persistence import JsonFile, data_path

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAMES = (
    "email_verification_link",
    "sms_otp",
    "resume_link",
    "submission_email",
    "submission_sms",
    "call_centre_case",
    # Review lifecycle (L4 §3.4)
    "review_assigned",
    "reupload_request",
    "reupload_received",
    "inquiry_rejected",
    "azure_ad_invitation",
    "first_level_approved",
    "contacts_request",
    "contacts_received",
    "sales_data_request",
    "sales_data_received",
    "request_withdrawn",
    "inquiry_accepted",
)
Channel = Literal["email", "sms"]
Kind = Literal["information", "action_required"]

_LINK_RE = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class MessageTemplate:
    name: str
    kind: Kind
    channel: Channel
    subject: str
    body: str


@dataclass(frozen=True)
class OutboxMessage:
    id: str
    inquiry_id: str
    channel: Channel
    to: str
    template: str
    kind: Kind
    subject: str
    body: str
    links: list[str]
    created_at: str


@lru_cache
def load_template(name: str) -> MessageTemplate:
    text = (TEMPLATE_DIR / f"{name}.txt").read_text(encoding="utf-8")
    header, _, body = text.partition("\n---\n")
    fields = dict(line.split(":", 1) for line in header.strip().splitlines() if ":" in line)
    kind = fields["kind"].strip()
    channel = fields["channel"].strip()
    if kind not in ("information", "action_required") or channel not in ("email", "sms"):
        msg = f"template {name}: bad kind or channel"
        raise ValueError(msg)
    return MessageTemplate(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        channel=channel,  # type: ignore[arg-type]
        subject=fields["subject"].strip(),
        body=body.strip() + "\n",
    )


# Used when the inquiry doesn't have the value yet (e.g. a link sent before the name).
DEFAULTS: dict[str, str] = {
    "first_name": "there",
    "brand": "your brand",
    "mall": "a Cenomi mall",
    "remarks": "",
    "reviewer_name": "there",
}


def render(name: str, context: dict[str, Any]) -> tuple[MessageTemplate, str, str]:
    template = load_template(name)
    values = {**DEFAULTS, **{k: "" if v is None else str(v) for k, v in context.items()}}
    subject = Template(template.subject).safe_substitute(values)
    body = Template(template.body).safe_substitute(values)
    return template, subject, body


class NotificationService(Protocol):
    async def send(
        self, template: str, to: str, context: dict[str, Any], *, inquiry_id: str
    ) -> str: ...


class MockNotificationService:
    """Delivers to an outbox (kept in memory, and in DATA_DIR when set)."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._file = JsonFile(data_path(data_dir, "mock_world", "outbox.json"))
        self._messages: list[dict[str, Any]] = list(self._file.load([]))
        self._lock = threading.Lock()

    async def send(
        self, template: str, to: str, context: dict[str, Any], *, inquiry_id: str
    ) -> str:
        spec, subject, body = render(template, context)
        message = OutboxMessage(
            id=f"msg_{uuid.uuid4().hex[:10]}",
            inquiry_id=inquiry_id,
            channel=spec.channel,
            to=to,
            template=spec.name,
            kind=spec.kind,
            subject=subject,
            body=body,
            links=_LINK_RE.findall(body),
            created_at=datetime.now(tz=UTC).isoformat(),
        )
        with self._lock:
            self._messages.append(asdict(message))
            self._file.save(self._messages)
        return message.id

    def messages(self, to: str | None = None) -> list[dict[str, Any]]:
        """Newest first; optionally only one recipient's."""
        with self._lock:
            items = [m for m in self._messages if to is None or m["to"] == to]
        return list(reversed(items))

    def clear(self) -> None:
        with self._lock:
            self._messages = []
            self._file.save(self._messages)
