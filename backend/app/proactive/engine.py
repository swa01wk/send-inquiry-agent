"""The trigger engine (L5 §3.1–3.2, thin): one `tick` evaluates every case.

Triggers (thresholds from `policy.proactive`):
- stalled review: first or second review past `review_stall_hours` → a queue item and a
  `review_stalled` email to the queue's reviewers (tier 0);
- escalation: past `review_escalate_hours` → a manager item and `review_escalated` to the
  region manager for that role (tier 0);
- unanswered request: a re-upload, contacts or sales-data request open past
  `tenant_reminder_hours` → a drafted reminder (tier 2, or 1 when pre-approved).

Each fires once per case per period (`AttentionItem.key`): a stay in one stage, or one
open request. A tick also sends held messages whose time has come, and resolves items
whose condition has passed. Nothing here calls `transition()` or saves a case.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app import clock
from app.agent.runtime import AgentRuntime
from app.domain.case_brief import STAGE_LABELS
from app.domain.fields import document_label
from app.domain.models import FieldKey
from app.policy.config import get_policy
from app.proactive.models import AttentionItem, Trigger
from app.proactive.notification_policy import NotificationPolicy, PolicyVerdict
from app.workflow.effects import applicant_context, send_message, send_to_applicant
from app.workflow.models import CONTACT_ROLE_LABELS, Case, CaseRequest, CaseStatus
from app.workflow.service import case_url, console_url

REVIEW_STAGES = (CaseStatus.FIRST_REVIEW, CaseStatus.SECOND_REVIEW)
ROLE_LABELS = {
    "rlm_store": "Regional Leasing Manager (Store)",
    "rplm_media": "Regional Property Leasing Manager (Media)",
    "rplm_specialty": "Regional Property Leasing Manager (Specialty)",
}


class ProactiveError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class TickResult:
    raised: list[AttentionItem] = field(default_factory=list)
    sent: list[AttentionItem] = field(default_factory=list)
    resolved: list[AttentionItem] = field(default_factory=list)


def stage_since(case: Case) -> datetime:
    """When the case entered its current status."""
    for event in reversed(case.events):
        if event.to_status == case.status:
            return event.at
    return case.submitted_at


def hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600


def _item_id(key: str) -> str:
    return "att_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _audit_decision(
    runtime: AgentRuntime,
    item: AttentionItem,
    decision: str,
    *,
    by: str = "system",
    reason: str | None = None,
) -> None:
    runtime.services.audit.record(
        item.case_id,
        "proactive_decision",
        actor="reviewer" if by != "system" else "system",
        payload={
            "item_id": item.id,
            "trigger": item.trigger,
            "decision": decision,
            "reason": reason,
            "by": by,
        },
    )


def default_reminder_text(case: Case, request: CaseRequest) -> str:
    """The plain reminder (L5 §3.5's fallback): what's missing and the reviewer's note."""
    if request.kind == "reupload":
        documents = ", ".join(document_label(d) for d in request.doc_types) or "documents"
        what = f"the documents they asked for ({documents})"
    elif request.kind == "contacts":
        roles = " and ".join(
            CONTACT_ROLE_LABELS[r] for r in get_policy().second_level_contacts.required
        )
        what = f"your company contacts ({roles})"
    else:
        what = "your estimated sales data"
    text = f"The leasing team is still waiting for {what} on your inquiry {case.reference}."
    if request.remarks.strip():
        text += f" Their note: “{request.remarks.strip()}”"
    return text


def _new_item(
    case: Case,
    trigger: Trigger,
    key: str,
    *,
    since: datetime,
    threshold: int,
    tier: int,
    now: datetime,
    request: CaseRequest | None = None,
) -> AttentionItem:
    queue = case.review_queue
    assert queue is not None
    return AttentionItem(
        id=_item_id(key),
        key=key,
        trigger=trigger,
        case_id=case.id,
        queue_role=queue.role,
        queue_region=queue.region,
        audience="manager" if trigger == "escalation" else "queue",
        stage=case.status.value,
        since=since,
        threshold_hours=threshold,
        tier=tier,
        raised_at=now,
        request_id=request.id if request else None,
        request_kind=request.kind if request else None,
    )


def _staff_context(
    runtime: AgentRuntime, case: Case, item: AttentionItem, now: datetime
) -> dict[str, Any]:
    queue = case.review_queue
    return applicant_context(
        runtime,
        case,
        hours=int(hours_between(item.since, now)),
        threshold_hours=item.threshold_hours,
        stage_label=STAGE_LABELS.get(item.stage, item.stage),
        queue_label=(
            f"{ROLE_LABELS.get(queue.role, queue.role)}, {queue.region.capitalize()}"
            if queue
            else ""
        ),
        console_url=console_url(runtime, case),
    )


async def _flag_staff(
    runtime: AgentRuntime, case: Case, item: AttentionItem, now: datetime
) -> None:
    """Tier 0: email the queue (stalled) or the role's managers (escalation)."""
    reviewers = runtime.services.reviewers
    if item.trigger == "escalation":
        recipients = [r for r in reviewers.all() if r.manager and r.role == item.queue_role]
        template = "review_escalated"
    else:
        recipients = [
            r for r in reviewers.for_queue(item.queue_role, item.queue_region) if not r.manager
        ]
        template = "review_stalled"
    context = _staff_context(runtime, case, item, now)
    for reviewer in recipients:
        await send_message(
            runtime,
            case,
            template,
            reviewer.email,
            {**context, "reviewer_name": reviewer.name.split()[0]},
        )
    _audit_decision(runtime, item, "sent", reason=f"{len(recipients)} recipient(s)")


def _last_applicant_message(runtime: AgentRuntime, case_id: str) -> datetime | None:
    sent = [
        i.sent_at
        for i in runtime.services.attention.all()
        if i.case_id == case_id and i.trigger == "applicant_reminder" and i.sent_at
    ]
    return max(sent) if sent else None


async def deliver_reminder(
    runtime: AgentRuntime, case: Case, item: AttentionItem, now: datetime
) -> AttentionItem:
    await send_to_applicant(
        runtime,
        case,
        "applicant_reminder",
        message=item.text or "",
        case_url=case_url(runtime, case, item.request_id),
    )
    item.status = "sent"
    item.sent_at = now
    item.send_after = None
    runtime.services.attention.save(item)
    _audit_decision(runtime, item, "sent", by=item.decided_by or "system")
    return item


async def apply_verdict(
    runtime: AgentRuntime, case: Case, item: AttentionItem, verdict: PolicyVerdict, now: datetime
) -> AttentionItem:
    """Send, hold (quiet hours or throttle) or wait for approval, and audit which."""
    if verdict.decision == "send":
        return await deliver_reminder(runtime, case, item, now)
    if verdict.decision == "awaiting_approval":
        item.status = "awaiting_approval"
    else:
        item.status = "held"
        item.send_after = verdict.send_after
    runtime.services.attention.save(item)
    _audit_decision(runtime, item, verdict.decision, by=item.decided_by or "system")
    return item


def _still_relevant(item: AttentionItem, case: Case | None) -> bool:
    if case is None:
        return False
    if item.trigger == "applicant_reminder":
        return any(r.id == item.request_id and r.status == "open" for r in case.requests)
    return case.status.value == item.stage and stage_since(case) == item.since


async def tick(runtime: AgentRuntime, *, now: datetime | None = None) -> TickResult:
    """Evaluate every trigger once. Safe to repeat: each firing is keyed per period."""
    current = now or clock.now()
    policy = get_policy().proactive
    store = runtime.services.attention
    gate = NotificationPolicy(policy)
    result = TickResult()
    cases = {c.id: c for c in runtime.services.cases.all()}

    # Items whose condition passed (the reviewer acted, the applicant answered).
    for item in store.all():
        if item.status in ("open", "awaiting_approval", "held") and not _still_relevant(
            item, cases.get(item.case_id)
        ):
            item.status = "dismissed"
            item.dismissed_reason = "resolved"
            store.save(item)
            _audit_decision(runtime, item, "resolved")
            result.resolved.append(item)

    for case in cases.values():
        if case.review_queue is None:
            continue
        if case.status in REVIEW_STAGES:
            since = stage_since(case)
            age = hours_between(since, current)
            stage_triggers: tuple[tuple[Trigger, int], ...] = (
                ("stalled_review", policy.review_stall_hours),
                ("escalation", policy.review_escalate_hours),
            )
            for trigger, threshold in stage_triggers:
                key = f"{case.id}:{trigger}:{case.status.value}:{since.isoformat()}"
                if age < threshold or store.has_key(key):
                    continue
                item = _new_item(
                    case, trigger, key, since=since, threshold=threshold, tier=0, now=current
                )
                store.save(item)
                _raised(runtime, item, age)
                await _flag_staff(runtime, case, item, current)
                result.raised.append(item)
        for request in case.requests:
            if request.status != "open":
                continue
            age = hours_between(request.requested_at, current)
            key = f"{case.id}:applicant_reminder:{request.id}"
            if age < policy.tenant_reminder_hours or store.has_key(key):
                continue
            item = _new_item(
                case,
                "applicant_reminder",
                key,
                since=request.requested_at,
                threshold=policy.tenant_reminder_hours,
                tier=1 if policy.reminder_pre_approved else 2,
                now=current,
                request=request,
            )
            item.text = default_reminder_text(case, request)
            store.save(item)
            _raised(runtime, item, age)
            verdict = gate.check(
                tier=item.tier,
                now=current,
                last_applicant_message=_last_applicant_message(runtime, case.id),
            )
            item = await apply_verdict(runtime, case, item, verdict, current)
            result.raised.append(item)
            if item.status == "sent":
                result.sent.append(item)

    # Held messages whose time has come.
    for item in store.all():
        if item.status != "held" or item.send_after is None or item.send_after > current:
            continue
        held_case = cases.get(item.case_id)
        if held_case is None:
            continue
        verdict = gate.check(
            tier=item.tier,
            now=current,
            approved=True,
            last_applicant_message=_last_applicant_message(runtime, held_case.id),
        )
        item = await apply_verdict(runtime, held_case, item, verdict, current)
        if item.status == "sent":
            result.sent.append(item)
    return result


def _raised(runtime: AgentRuntime, item: AttentionItem, age: float) -> None:
    runtime.services.audit.record(
        item.case_id,
        "proactive_raised",
        actor="system",
        payload={
            "item_id": item.id,
            "trigger": item.trigger,
            "tier": item.tier,
            "stage": item.stage,
            "hours": int(age),
        },
    )


def _case_for_item(runtime: AgentRuntime, item: AttentionItem) -> Case:
    case = runtime.services.cases.get(item.case_id)
    if case is None:
        raise ProactiveError(404, "case_not_found", "That case no longer exists.")
    return case


async def approve(
    runtime: AgentRuntime, item_id: str, *, by: str, text: str | None = None
) -> AttentionItem:
    """A reviewer approves a drafted reminder (optionally edited). Quiet hours and the
    throttle still apply: it may be held until it's allowed to go."""
    store = runtime.services.attention
    item = store.get(item_id)
    if item is None:
        raise ProactiveError(404, "item_not_found", "No such item.")
    if item.trigger != "applicant_reminder" or item.status != "awaiting_approval":
        raise ProactiveError(409, "not_awaiting_approval", "This item isn't waiting for approval.")
    case = _case_for_item(runtime, item)
    if not _still_relevant(item, case):
        raise ProactiveError(409, "request_closed", "The request was answered or withdrawn.")
    if text is not None:
        cleaned = text.strip()
        if not cleaned or len(cleaned) > 1000:
            raise ProactiveError(400, "invalid_text", "The reminder needs 1–1000 characters.")
        item.text = cleaned
    if not (case.draft.fields[FieldKey.EMAIL].value):
        raise ProactiveError(409, "no_email", "The applicant has no email address.")
    item.decided_by = by
    now = clock.now()
    verdict = NotificationPolicy(get_policy().proactive).check(
        tier=item.tier,
        now=now,
        approved=True,
        last_applicant_message=_last_applicant_message(runtime, case.id),
    )
    return await apply_verdict(runtime, case, item, verdict, now)


def dismiss(runtime: AgentRuntime, item_id: str, *, by: str, reason: str) -> AttentionItem:
    store = runtime.services.attention
    item = store.get(item_id)
    if item is None:
        raise ProactiveError(404, "item_not_found", "No such item.")
    if reason not in get_policy().proactive.dismiss_reasons:
        raise ProactiveError(400, "invalid_reason", "Pick one of the listed reasons.")
    if item.status in ("sent", "dismissed"):
        raise ProactiveError(409, "already_closed", "This item is already closed.")
    item.status = "dismissed"
    item.dismissed_reason = reason
    item.decided_by = by
    item.send_after = None
    store.save(item)
    _audit_decision(runtime, item, "dismissed", by=by, reason=reason)
    return item
