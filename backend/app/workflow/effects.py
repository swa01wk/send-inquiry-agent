"""Side effects of lifecycle events (L4 §3.4), run inline after the transition is saved.

Each effect is keyed by `(case id, event seq, effect)` and recorded on the case once it
has run, so a retry never sends twice. A failed effect is audited (`effect_run`) and
never rolls back the transition. Sprint 2 moves this to a `case_effects` outbox with a
worker.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from app.agent.context import message_context
from app.domain.fields import document_label
from app.domain.models import FieldKey
from app.domain.payload import lead_payload
from app.gateway import GatewayError
from app.policy.config import get_policy
from app.workflow.machine import SYSTEM
from app.workflow.models import Case, WorkflowEvent
from app.workflow.service import apply_event, case_url, console_url

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime

logger = logging.getLogger(__name__)

Effect = Callable[["AgentRuntime", Case, WorkflowEvent], Awaitable[Case]]
REQUEST_LABELS = {
    "reupload": "documents",
    "contacts": "company contacts",
    "sales_data": "sales data",
}


def _applicant_context(runtime: AgentRuntime, case: Case, **extra: Any) -> dict[str, Any]:
    return {
        **message_context(case.draft, runtime.master),
        "reference": case.reference,
        "after_rejection": get_policy().after_rejection,
        **extra,
    }


async def _send(
    runtime: AgentRuntime, case: Case, template: str, to: str, context: dict[str, Any]
) -> None:
    send = functools.partial(runtime.services.notifications.send, inquiry_id=case.id)
    await runtime.services.gateway.call(
        "notifications", "send", send, template, to, context, inquiry_id=case.id
    )


async def _to_applicant(runtime: AgentRuntime, case: Case, template: str, **extra: Any) -> None:
    email = case.draft.fields[FieldKey.EMAIL].value
    if not email:
        return
    await _send(runtime, case, template, str(email), _applicant_context(runtime, case, **extra))


async def _to_reviewers(runtime: AgentRuntime, case: Case, template: str) -> None:
    queue = case.review_queue
    if queue is None:
        return
    for reviewer in runtime.services.reviewers.for_queue(queue.role, queue.region):
        if reviewer.manager:
            continue
        context = _applicant_context(
            runtime,
            case,
            reviewer_name=reviewer.name.split()[0],
            console_url=console_url(runtime, case),
        )
        await _send(runtime, case, template, reviewer.email, context)


def _latest_request(case: Case, kind: str | None = None):  # type: ignore[no-untyped-def]
    requests = [r for r in case.requests if kind is None or r.kind == kind]
    return requests[-1] if requests else None


def _notify_reviewers(template: str) -> Effect:
    async def run(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
        await _to_reviewers(runtime, case, template)
        return case

    return run


def _request_email(template: str, kind: str) -> Effect:
    async def run(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
        request = _latest_request(case, kind)
        if request is None:
            return case
        documents = "\n".join(f"- {document_label(d)}" for d in request.doc_types)
        await _to_applicant(
            runtime,
            case,
            template,
            remarks=request.remarks,
            documents=documents,
            case_url=case_url(runtime, case, request.id),
        )
        return case

    return run


async def _rejection_email(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    decision = case.decisions[-1] if case.decisions else None
    await _to_applicant(
        runtime,
        case,
        "inquiry_rejected",
        remarks=decision.remarks if decision else "",
        case_url=case_url(runtime, case),
    )
    return case


async def _invite(
    runtime: AgentRuntime, case: Case, email: str, first_name: str, role: str
) -> Case:
    identity = runtime.services.identity
    if identity.has_account(email):
        return case
    if any(i.email.lower() == email.lower() for i in case.onboarding.invitations):
        return case
    invitation = await runtime.services.gateway.call(
        "identity",
        "invite",
        functools.partial(identity.invite, inquiry_id=case.id),
        email,
        role,
        {**message_context(case.draft, runtime.master), "first_name": first_name},
        inquiry_id=case.id,
    )
    fresh = runtime.services.cases.get(case.id) or case
    fresh.onboarding.invitations.append(invitation)
    runtime.services.cases.save(fresh)
    return fresh


async def _invite_primary(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    email = case.draft.fields[FieldKey.EMAIL].value
    first = case.draft.fields[FieldKey.FIRST_NAME].value
    if not email:
        return case
    return await _invite(runtime, case, str(email), str(first or "there"), "primary_contact")


async def _first_level_email(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    await _to_applicant(runtime, case, "first_level_approved", case_url=case_url(runtime, case))
    return case


async def _auto_contacts_request(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    """Requirements §7.1.1 b: "on contact creation", a request for more tenant contacts."""
    if not get_policy().auto_request_contacts_after_first_approval:
        return case
    if case.open_request("contacts") is not None:
        return case
    return await apply_event(
        runtime,
        case.id,
        WorkflowEvent(name="contacts_requested", payload={"remarks": ""}),
        SYSTEM,
    )


async def _withdrawn_email(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    kind = str(event.payload.get("kind", ""))
    await _to_applicant(
        runtime,
        case,
        "request_withdrawn",
        request_label=REQUEST_LABELS.get(kind, "information"),
        case_url=case_url(runtime, case),
    )
    return case


async def _invite_contacts(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    for contact in case.tenant_contacts:
        email = contact.email.value
        if not email or contact.same_as_primary:
            continue
        case = await _invite(
            runtime, case, str(email), str(contact.first_name.value or "there"), contact.role
        )
    return case


async def _accepted_email(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    await _to_applicant(runtime, case, "inquiry_accepted", case_url=case_url(runtime, case))
    return case


async def _send_lead(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    """Send to Yardi; each failure is a `yardi_failed` event. Nobody is told it was sent
    until Yardi acknowledges (L4 §3.7). After YARDI_MAX_ATTEMPTS, flag for operations."""
    services = runtime.services
    payload = lead_payload(case, runtime.master)
    for _attempt in range(runtime.settings.yardi_max_attempts):
        try:
            lead_ref = services.gateway.call_sync(
                "yardi",
                "send_lead",
                services.yardi.send_lead,
                payload,
                idempotency_key=f"lead:{case.id}",
                inquiry_id=case.id,
            )
        except GatewayError as err:
            case = await apply_event(
                runtime,
                case.id,
                WorkflowEvent(name="yardi_failed", payload={"kind": err.kind}),
                SYSTEM,
            )
            continue
        return await apply_event(
            runtime,
            case.id,
            WorkflowEvent(name="sent_to_yardi", payload={"lead_ref": lead_ref}),
            SYSTEM,
        )
    fresh = services.cases.get(case.id) or case
    fresh.yardi.needs_operations = True
    services.cases.save(fresh)
    return fresh


EFFECTS: dict[str, list[tuple[str, Effect]]] = {
    "routed": [("review_assigned", _notify_reviewers("review_assigned"))],
    "reupload_requested": [("reupload_request", _request_email("reupload_request", "reupload"))],
    "documents_resubmitted": [("reupload_received", _notify_reviewers("reupload_received"))],
    "rejected": [("inquiry_rejected", _rejection_email)],
    "approved_first": [
        ("invite_primary", _invite_primary),
        ("first_level_approved", _first_level_email),
        ("auto_contacts_request", _auto_contacts_request),
    ],
    "contacts_requested": [("contacts_request", _request_email("contacts_request", "contacts"))],
    "contacts_provided": [("contacts_received", _notify_reviewers("contacts_received"))],
    "sales_data_requested": [
        ("sales_data_request", _request_email("sales_data_request", "sales_data"))
    ],
    "sales_data_provided": [("sales_data_received", _notify_reviewers("sales_data_received"))],
    "request_withdrawn": [("request_withdrawn", _withdrawn_email)],
    "approved": [
        ("invite_contacts", _invite_contacts),
        ("inquiry_accepted", _accepted_email),
        ("send_lead", _send_lead),
    ],
}


async def run_effects(runtime: AgentRuntime, case: Case, event: WorkflowEvent) -> Case:
    """Run the event's effects that haven't run for this event yet. Returns the latest case."""
    seq = case.event_seq
    for name, effect in EFFECTS.get(event.name, []):
        key = f"{case.id}:{seq}:{name}"
        current = runtime.services.cases.get(case.id) or case
        if key in current.effects_done:
            continue
        outcome = "done"
        try:
            case = await effect(runtime, current, event)
        except GatewayError as err:
            outcome = err.kind
            case = current
        except Exception:
            logger.exception("effect %s failed for %s", name, case.id)
            outcome = "error"
            case = current
        if outcome == "done":
            latest = runtime.services.cases.get(case.id) or case
            latest.effects_done.append(key)
            runtime.services.cases.save(latest)
            case = latest
        runtime.services.audit.record(
            case.id,
            "effect_run",
            actor="system",
            payload={"effect": name, "event": event.name, "outcome": outcome},
        )
    return runtime.services.cases.get(case.id) or case


# Shared with proactive work (app/proactive/engine.py): the same context and delivery path.
applicant_context = _applicant_context
send_message = _send
send_to_applicant = _to_applicant
