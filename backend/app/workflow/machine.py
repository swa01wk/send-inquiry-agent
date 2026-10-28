"""The inquiry state machine (M0 §6): a pure function, no library.

`transition(case, event, actor=…, now=…)` returns the updated case or raises
`IllegalTransition`. It never sends anything: effects run after the transition is
persisted (`app/workflow/effects.py`). Callers audit every call, legal or not
(`app/workflow/service.py`).

Reviewer events also check the actor: a reviewer whose role and regions match the case's
review queue. The machine enforces this, not the console.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from app.domain.models import DocType, DocumentRef
from app.policy.config import get_policy
from app.workflow.models import (
    Case,
    CaseEvent,
    CaseRequest,
    CaseStatus,
    Decision,
    RequestKind,
    ReviewQueue,
    TenantContact,
    WorkflowEvent,
)

ActorKind = Literal["user", "system", "reviewer", "staff"]


class Actor(BaseModel):
    kind: ActorKind
    id: str | None = None
    role: str | None = None  # reviewers: rlm_store | rplm_media | rplm_specialty
    regions: list[str] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.id}" if self.id else self.kind


USER = Actor(kind="user")
SYSTEM = Actor(kind="system")


class IllegalTransition(Exception):
    """`code`: illegal_transition | not_in_queue | not_allowed | invalid_payload."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


S = CaseStatus

# (from, event) → (to, who may trigger). Reviewer rows also check the queue.
TABLE: dict[tuple[CaseStatus, str], tuple[CaseStatus, frozenset[ActorKind]]] = {
    (S.DRAFT, "submit_requested"): (S.SUBMITTING, frozenset({"user", "staff"})),
    (S.SUBMITTING, "submit_succeeded"): (S.SUBMITTED, frozenset({"system"})),
    (S.SUBMITTING, "submit_failed"): (S.DRAFT, frozenset({"system"})),
    (S.SUBMITTING, "submit_unknown"): (S.SUBMITTING, frozenset({"system"})),
    (S.DRAFT, "expired"): (S.ABANDONED, frozenset({"system"})),
    (S.DRAFT, "redirected_to_sign_in"): (S.REDIRECTED, frozenset({"system", "staff"})),
    (S.SUBMITTED, "routed"): (S.FIRST_REVIEW, frozenset({"system"})),
    (S.FIRST_REVIEW, "reupload_requested"): (S.REUPLOAD_REQUESTED, frozenset({"reviewer"})),
    (S.REUPLOAD_REQUESTED, "documents_resubmitted"): (S.FIRST_REVIEW, frozenset({"user"})),
    (S.FIRST_REVIEW, "rejected"): (S.REJECTED, frozenset({"reviewer"})),
    (S.FIRST_REVIEW, "approved_first"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contacts_requested"): (S.SECOND_REVIEW, frozenset({"reviewer", "system"})),
    (S.SECOND_REVIEW, "sales_data_requested"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contact_removed"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contacts_provided"): (S.SECOND_REVIEW, frozenset({"user"})),
    (S.SECOND_REVIEW, "sales_data_provided"): (S.SECOND_REVIEW, frozenset({"user"})),
    (S.SECOND_REVIEW, "request_withdrawn"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "company_relinked"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "brand_relinked"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "rejected"): (S.REJECTED, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "approved"): (S.APPROVED, frozenset({"reviewer"})),
    (S.APPROVED, "sent_to_yardi"): (S.SENT_TO_YARDI, frozenset({"system"})),
    (S.APPROVED, "yardi_failed"): (S.APPROVED, frozenset({"system"})),
}

# The console's actions (L4 §3.3), each one state-machine event.
REVIEWER_EVENTS = frozenset(
    event for (_from, event), (_to, who) in TABLE.items() if "reviewer" in who
)


def _invalid(message: str) -> IllegalTransition:
    return IllegalTransition("invalid_payload", message)


def _remarks(payload: dict[str, Any], *, required: bool) -> str:
    remarks = str(payload.get("remarks") or "").strip()
    if required and not remarks:
        raise _invalid("Remarks are required.")
    return remarks


def _check_actor(case: Case, event: str, who: frozenset[ActorKind], actor: Actor) -> None:
    if actor.kind not in who:
        raise IllegalTransition(
            "not_allowed", f"{event} can't be triggered by {actor.kind} in status {case.status}."
        )
    if actor.kind != "reviewer":
        return
    queue = case.review_queue
    if queue is None or actor.role != queue.role or queue.region not in actor.regions:
        raise IllegalTransition("not_in_queue", "This case isn't in your review queue.")


def legal_events(case: Case, actor: Actor) -> list[str]:
    """Events this actor could fire now (guards on payloads aside): the console's actions."""
    events: list[str] = []
    for (from_status, event), (_to, who) in TABLE.items():
        if from_status != case.status:
            continue
        try:
            _check_actor(case, event, who, actor)
        except IllegalTransition:
            continue
        if event in ("contacts_requested", "sales_data_requested"):
            kind: RequestKind = "contacts" if event == "contacts_requested" else "sales_data"
            if case.open_request(kind) is not None:
                continue
        if event == "request_withdrawn" and not any(r.status == "open" for r in case.requests):
            continue
        if event == "approved" and _approval_blockers(case):
            continue
        if event == "contact_removed" and not case.tenant_contacts:
            continue
        events.append(event)
    return events


def _approval_blockers(case: Case) -> list[str]:
    blockers = [f"open_request:{r.kind}" for r in case.requests if r.status == "open"]
    policy = get_policy()
    if policy.require_contacts_before_approval:
        present = {c.role for c in case.tenant_contacts}
        for role in policy.second_level_contacts.required:
            if role not in present:
                blockers.append(f"missing_contact:{role}")
    return blockers


def approval_blockers(case: Case) -> list[str]:
    return _approval_blockers(case)


def _new_request(
    case: Case, kind: str, actor: Actor, now: datetime, payload: dict[str, Any], **extra: Any
) -> CaseRequest:
    return CaseRequest(
        id=f"req_{uuid.uuid4().hex[:10]}",
        kind=cast(RequestKind, kind),
        remarks=_remarks(payload, required=False),
        requested_by=actor.id or actor.kind,
        requested_at=now,
        **extra,
    )


def _close(request: CaseRequest, status: str, now: datetime) -> None:
    request.status = cast(Literal["open", "fulfilled", "withdrawn"], status)
    request.closed_at = now


# ---- per-event effects on the case data (guards raise IllegalTransition) ------------


def _routed(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    raw = event.payload.get("queue")
    if not isinstance(raw, dict):
        raise _invalid("A review queue is required.")
    case.review_queue = ReviewQueue.model_validate(raw)


def _reupload_requested(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    raw = event.payload.get("doc_types")
    if not isinstance(raw, list) or not raw:
        raise _invalid("Pick at least one document to re-upload.")
    try:
        doc_types = list(dict.fromkeys(DocType(str(d)) for d in raw))
    except ValueError as exc:
        raise _invalid("Unknown document type.") from exc
    if DocType.SALES_DATA in doc_types:
        raise _invalid("Sales data is requested on its own, not as a re-upload.")
    remarks = _remarks(event.payload, required=True)
    case.requests.append(
        CaseRequest(
            id=f"req_{uuid.uuid4().hex[:10]}",
            kind="reupload",
            doc_types=doc_types,
            remarks=remarks,
            requested_by=actor.id or actor.kind,
            requested_at=now,
        )
    )


def _documents_resubmitted(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    request = case.open_request("reupload")
    if request is None:
        raise _invalid("There's no open re-upload request.")
    raw = event.payload.get("documents")
    if not isinstance(raw, dict):
        raise _invalid("The re-uploaded documents are required.")
    replaced: dict[DocType, DocumentRef] = {}
    missing: list[str] = []
    for doc_type in request.doc_types:
        ref_raw = raw.get(doc_type.value)
        ref = DocumentRef.model_validate(ref_raw) if ref_raw else None
        if ref is None or ref.uploaded_at <= request.requested_at:
            missing.append(doc_type.value)
        else:
            replaced[doc_type] = ref
    if missing:
        raise _invalid(f"Not re-uploaded yet: {', '.join(missing)}.")
    for doc_type, ref in replaced.items():
        previous = case.draft.documents.get(doc_type)
        if previous is not None:
            case.document_history.append(previous)
        case.draft.documents[doc_type] = ref
    _close(request, "fulfilled", now)


def _rejected(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    remarks = _remarks(event.payload, required=True)
    category = event.payload.get("reason_category")
    categories = get_policy().rejection_categories
    if category is not None and category not in categories:
        raise _invalid("Unknown reason category.")
    level = "first" if case.status == S.FIRST_REVIEW else "second"
    case.decisions.append(
        Decision(
            level=level,
            outcome="rejected",
            remarks=remarks,
            reason_category=category,
            by=actor.id or actor.kind,
            at=now,
        )
    )
    for request in case.requests:
        if request.status == "open":
            _close(request, "withdrawn", now)


def _approved_first(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    case.decisions.append(
        Decision(
            level="first",
            outcome="approved",
            remarks=_remarks(event.payload, required=False) or None,
            by=actor.id or actor.kind,
            at=now,
        )
    )


def _request(kind: str) -> Callable[[Case, WorkflowEvent, Actor, datetime], None]:
    def apply(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
        if case.open_request(cast(RequestKind, kind)) is not None:
            raise _invalid(f"A {kind.replace('_', ' ')} request is already open.")
        case.requests.append(_new_request(case, kind, actor, now, event.payload))

    return apply


def _contact_removed(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    role = event.payload.get("role")
    before = len(case.tenant_contacts)
    case.tenant_contacts = [c for c in case.tenant_contacts if c.role != role]
    if len(case.tenant_contacts) == before:
        raise _invalid("There's no contact with that role.")


def _contacts_provided(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    request = case.open_request("contacts")
    if request is None:
        raise _invalid("There's no open contacts request.")
    raw = event.payload.get("contacts")
    if not isinstance(raw, list):
        raise _invalid("Contacts are required.")
    contacts = [TenantContact.model_validate(c) for c in raw]
    present = {c.role for c in contacts}
    missing = [r for r in get_policy().second_level_contacts.required if r not in present]
    if missing:
        raise _invalid(f"Missing required contacts: {', '.join(missing)}.")
    case.tenant_contacts = contacts
    _close(request, "fulfilled", now)


def _sales_data_provided(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    request = case.open_request("sales_data")
    if request is None:
        raise _invalid("There's no open sales data request.")
    raw = event.payload.get("document")
    if not raw:
        raise _invalid("The sales data file is required.")
    ref = DocumentRef.model_validate(raw)
    if case.sales_data is not None:
        case.document_history.append(case.sales_data)
    case.sales_data = ref
    _close(request, "fulfilled", now)


def _request_withdrawn(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    kind = event.payload.get("kind")
    request = (
        case.open_request(cast(RequestKind, kind)) if kind in ("contacts", "sales_data") else None
    )
    if request is None:
        raise _invalid("There's no open request of that kind.")
    _close(request, "withdrawn", now)


def _company_relinked(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    company_id = str(event.payload.get("company_id") or "").strip()
    if not company_id:
        raise _invalid("A Yardi company is required.")
    case.yardi.company_id = company_id
    case.yardi.brand_id = None  # a brand belongs to one company


def _brand_relinked(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    brand_id = str(event.payload.get("brand_id") or "").strip()
    if not brand_id:
        raise _invalid("A Yardi brand is required.")
    if case.yardi.company_id is None:
        raise _invalid("Re-link the company first.")
    case.yardi.brand_id = brand_id


def _approved(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    blockers = _approval_blockers(case)
    if blockers:
        raise _invalid(f"Can't approve yet: {', '.join(blockers)}.")
    case.decisions.append(
        Decision(
            level="second",
            outcome="approved",
            remarks=_remarks(event.payload, required=False) or None,
            by=actor.id or actor.kind,
            at=now,
        )
    )


def _sent_to_yardi(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    lead_ref = str(event.payload.get("lead_ref") or "")
    if not lead_ref:
        raise _invalid("Yardi's lead reference is required.")
    case.yardi.lead_ref = lead_ref
    case.yardi.sent_at = now
    case.yardi.needs_operations = False


def _yardi_failed(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    case.yardi.attempts += 1


def _noop(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    return None


APPLY: dict[str, Callable[[Case, WorkflowEvent, Actor, datetime], None]] = {
    "routed": _routed,
    "reupload_requested": _reupload_requested,
    "documents_resubmitted": _documents_resubmitted,
    "rejected": _rejected,
    "approved_first": _approved_first,
    "contacts_requested": _request("contacts"),
    "sales_data_requested": _request("sales_data"),
    "contact_removed": _contact_removed,
    "contacts_provided": _contacts_provided,
    "sales_data_provided": _sales_data_provided,
    "request_withdrawn": _request_withdrawn,
    "company_relinked": _company_relinked,
    "brand_relinked": _brand_relinked,
    "approved": _approved,
    "sent_to_yardi": _sent_to_yardi,
    "yardi_failed": _yardi_failed,
}


def transition(case: Case, event: WorkflowEvent, *, actor: Actor, now: datetime) -> Case:
    """The case after `event`, or IllegalTransition. The input case is not changed."""
    row = TABLE.get((case.status, event.name))
    if row is None:
        raise IllegalTransition(
            "illegal_transition", f"{event.name} isn't possible while the case is {case.status}."
        )
    to_status, who = row
    _check_actor(case, event.name, who, actor)
    updated: Case = case.model_copy(deep=True)
    APPLY.get(event.name, _noop)(updated, event, actor, now)
    updated.events.append(
        CaseEvent(
            seq=updated.event_seq + 1,
            name=event.name,
            from_status=case.status,
            to_status=to_status,
            actor=actor.label,
            at=now,
        )
    )
    updated.status = to_status
    return updated
