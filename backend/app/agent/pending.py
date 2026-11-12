"""The flow v2 pending inquiry (spec flow-v2-alignment §3.3, FV12, FV13; day F3).

When verification succeeds on a v2 public inquiry, it becomes `pending` (the repository
sets the status on save: verified, not submitted). Nothing else moves: no reference, no
routing, no tracking email. It is abandoned after `pending_inquiry_ttl_minutes` since
`verified_at`. "Continue my inquiry" + the email (`resume_pending`, never sent to the
model) emails a link that re-verifies the email and resumes the chat; the reply is the
same whether or not one exists.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app import clock
from app.audit import AuditLog
from app.domain.models import FieldKey, InquiryDraft
from app.domain.rules import contact_verified
from app.policy.config import get_policy
from app.workflow.flow import FlowNode, record_flow_step_audit

RESUME_PENDING_REPLY = (
    "If there's an inquiry in progress for that email, we've sent you a link to continue."
)


def note_verification(
    audit: AuditLog,
    *,
    inquiry_id: str,
    draft: InquiryDraft,
    verified_before: bool,
    succeeded: bool,
    channel: str = "self_service",
) -> None:
    """Chart step Success? (`succ1`) for a v2 inquiry, and `inquiry_pending` the first time
    the contact is fully verified."""
    if draft.intake_flow != "v2" or draft.reference:
        return
    if not succeeded:
        # Chart: Success? no → back to Email/Mobile Verification.
        record_flow_step_audit(audit, inquiry_id=inquiry_id, node=FlowNode.SUCC1, outcome="no")
        record_flow_step_audit(audit, inquiry_id=inquiry_id, node=FlowNode.EMV)
        return
    if verified_before or not contact_verified(draft):
        return
    record_flow_step_audit(audit, inquiry_id=inquiry_id, node=FlowNode.SUCC1, outcome="yes")
    audit.record(inquiry_id, "inquiry_pending", actor="system", payload={"channel": channel})


def note_verification_sent(audit: AuditLog, *, inquiry_id: str, draft: InquiryDraft) -> None:
    """Chart step Email/Mobile Verification (`emv`): each send that went out."""
    if draft.intake_flow == "v2" and not draft.reference:
        record_flow_step_audit(audit, inquiry_id=inquiry_id, node=FlowNode.EMV)


def pending_ttl() -> timedelta:
    return timedelta(minutes=get_policy().flow_v2_intake.pending_inquiry_ttl_minutes)


def pending_expired(draft: InquiryDraft, now: datetime | None = None) -> bool:
    """A pending inquiry (v2, verified, not submitted) past its TTL since `verified_at`."""
    if draft.intake_flow != "v2" or draft.reference or draft.verified_at is None:
        return False
    return (now or clock.now()) - draft.verified_at > pending_ttl()


def is_pending(draft: InquiryDraft) -> bool:
    return (
        draft.intake_flow == "v2"
        and not draft.reference
        and draft.verified_at is not None
        and draft.cr_status != "existing"
    )


def verified_email(draft: InquiryDraft) -> str | None:
    value = draft.fields[FieldKey.EMAIL].value
    return str(value).strip().lower() if value and draft.email_verified else None


def normalise_email(raw: Any) -> str | None:
    text = str(raw or "").strip().lower()
    return text if "@" in text and len(text) <= 254 else None
