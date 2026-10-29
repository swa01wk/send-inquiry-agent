"""Attention items: one per trigger firing, keyed by (case, trigger, period)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Trigger = Literal["stalled_review", "escalation", "applicant_reminder"]
ItemStatus = Literal["open", "awaiting_approval", "held", "sent", "dismissed"]
Audience = Literal["queue", "manager"]

TRIGGER_LABELS: dict[str, str] = {
    "stalled_review": "Review is taking longer than the target",
    "escalation": "Escalated: still waiting for a decision",
    "applicant_reminder": "Request unanswered — reminder drafted",
}

RECOMMENDED: dict[str, str] = {
    "stalled_review": "Open the case and make the next decision.",
    "escalation": "Check with the queue, or decide the case.",
    "applicant_reminder": "Approve and send the reminder, edit it, or dismiss it.",
}


class AttentionItem(BaseModel):
    id: str
    key: str
    trigger: Trigger
    case_id: str
    queue_role: str
    queue_region: str
    audience: Audience
    stage: str  # the case status when it fired
    since: datetime  # when the stage was entered, or the request opened
    threshold_hours: int
    tier: int  # 0 internal, 1 pre-approved applicant message, 2 needs approval
    raised_at: datetime
    status: ItemStatus = "open"
    request_id: str | None = None
    request_kind: str | None = None
    text: str | None = None  # the reminder's message, editable before it goes
    send_after: datetime | None = None
    sent_at: datetime | None = None
    decided_by: str | None = None
    dismissed_reason: str | None = None
