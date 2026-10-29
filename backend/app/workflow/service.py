"""Apply lifecycle events: transition, persist, audit, then run the effects (L4 §3.4).

`apply_event` is the only way a case changes status. Console actions (reviewer), the
three applicant actions and system effects all go through it, so every transition, legal
or not, is in the audit trail with its actor.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app import clock
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft
from app.policy.config import get_policy
from app.security import tokens
from app.workflow.machine import SYSTEM, Actor, IllegalTransition, transition
from app.workflow.models import Case, CaseStatus, ReviewQueue, WorkflowEvent

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime


def route_queue(draft: InquiryDraft, master: MasterData) -> ReviewQueue | None:
    """Product line (unit type) and the mall's region → the review queue (policy routing)."""
    unit_type = draft.fields[FieldKey.UNIT_TYPE].value
    malls = draft.fields[FieldKey.MALLS].value
    if not unit_type or not isinstance(malls, list) or not malls:
        return None
    role = get_policy().review_routing.get(str(unit_type))
    mall = next((m for m in master.malls if m.id == malls[0]), None)
    if role is None or mall is None:
        return None
    city = next((c for c in master.cities if c.id == mall.city), None)
    region = mall.region or (city.region if city else None)
    if region is None:
        return None
    queue: ReviewQueue = ReviewQueue.model_validate(
        {"product_line": str(unit_type), "region": region, "role": role}
    )
    return queue


def case_url(runtime: AgentRuntime, case: Case, request_id: str | None = None) -> str:
    """`<PUBLIC_BASE_URL>/inquiry/case?t=…`: opens the case in chat (scoped to a request)."""
    settings = runtime.settings
    token, _claims = tokens.issue(
        settings.token_secret,
        "case",
        case.id,
        ttl_seconds=settings.case_ttl_days * 86400,
        data={"r": request_id} if request_id else {},
    )
    return f"{settings.public_base_url.rstrip('/')}/inquiry/case?t={token}"


def console_url(runtime: AgentRuntime, case: Case) -> str:
    return f"{runtime.settings.public_base_url.rstrip('/')}/review/cases/{case.id}"


def _audit_transition(
    runtime: AgentRuntime,
    case: Case,
    event: WorkflowEvent,
    actor: Actor,
    outcome: str,
    to_status: str | None,
) -> None:
    runtime.services.audit.record(
        case.id,
        "case_transition",
        actor="reviewer" if actor.kind == "reviewer" else actor.kind,
        payload={
            "event": event.name,
            "from_status": case.status.value,
            "to_status": to_status,
            "by": actor.id or actor.kind,
            "outcome": outcome,
        },
    )


async def apply_event(
    runtime: AgentRuntime,
    case_id: str,
    event: WorkflowEvent,
    actor: Actor,
    *,
    now: datetime | None = None,
) -> Case:
    """Transition and persist, then run the event's effects. Raises IllegalTransition."""
    from app.workflow.effects import run_effects  # local: effects call back into here

    store = runtime.services.cases
    case = store.get(case_id)
    if case is None:
        raise IllegalTransition("not_found", "Unknown case.")
    try:
        updated = transition(case, event, actor=actor, now=now or clock.now())
    except IllegalTransition as exc:
        _audit_transition(runtime, case, event, actor, exc.code, None)
        raise
    store.save(updated)
    _audit_transition(runtime, case, event, actor, "applied", updated.status.value)
    return await run_effects(runtime, updated, event)


async def create_case(
    runtime: AgentRuntime,
    *,
    session_id: str,
    inquiry_seq: int,
    draft: InquiryDraft,
    reference: str,
) -> Case:
    """The case for a submitted inquiry, routed to its review queue (event `routed`)."""
    store = runtime.services.cases
    existing = store.get(reference)
    if existing is not None:
        return existing
    case = Case(
        id=reference,
        reference=reference,
        session_id=session_id,
        inquiry_seq=inquiry_seq,
        status=CaseStatus.SUBMITTED,
        draft=draft.model_copy(deep=True),
        submitted_at=clock.now(),
    )
    store.save(case)
    runtime.services.audit.record(
        case.id, "case_created", actor="system", payload={"session": session_id}
    )
    queue = route_queue(draft, runtime.master)
    if queue is None:
        # Nothing to route on (shouldn't happen: unit type and mall are required).
        return case
    return await apply_event(
        runtime,
        case.id,
        WorkflowEvent(name="routed", payload={"queue": queue.model_dump()}),
        SYSTEM,
    )
