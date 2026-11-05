"""The inquiry state machine (M0 §6): a pure function, no library.

`transition(case, event, actor=…, now=…)` returns the updated case or raises
`IllegalTransition`. It never sends anything: effects run after the transition is
persisted (`app/workflow/effects.py`). Callers audit every call, legal or not
(`app/workflow/service.py`).

Reviewer events also check the actor: a reviewer whose regions include the queue's region
and whose role is the queue's role for that event's review level (`REVIEW_LEVEL`): the
first level (the Lease Admin, demo feedback §3.2) or the final level (RLM / RPLM). The
machine enforces this, not the console.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from app import clock
from app.domain.fields import document_label
from app.domain.models import NON_INTAKE_DOC_TYPES, DocType, DocumentRef
from app.policy.config import get_policy
from app.workflow.documents import current_decisions, document_blockers
from app.workflow.expiry import expiry_status, expiry_tracked
from app.workflow.models import (
    CONTACT_ROLE_LABELS,
    FIRST_LEVEL_STATES,
    Case,
    CaseEvent,
    CaseRequest,
    CaseStatus,
    Decision,
    DocumentDecision,
    RequestKind,
    ReviewLevel,
    ReviewQueue,
    TenantContact,
    WorkflowEvent,
)

ActorKind = Literal["user", "system", "reviewer", "staff"]


class Actor(BaseModel):
    kind: ActorKind
    id: str | None = None
    role: str | None = None  # reviewers: lease_admin | rlm_store | rplm_media | rplm_specialty
    regions: list[str] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.id}" if self.id else self.kind


USER = Actor(kind="user")
SYSTEM = Actor(kind="system")


class IllegalTransition(Exception):
    """`code`: illegal_transition | not_in_queue | not_allowed | invalid_payload |
    stale_file | stale_contact (the decision was made on a file or contact that has since
    been replaced: reload the case)."""

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
    # Per-document decisions (demo feedback §3.4): first level, also while a re-upload of
    # another document is awaited.
    (S.FIRST_REVIEW, "document_expiry_confirmed"): (S.FIRST_REVIEW, frozenset({"reviewer"})),
    (S.FIRST_REVIEW, "document_approved"): (S.FIRST_REVIEW, frozenset({"reviewer"})),
    (S.FIRST_REVIEW, "document_rejected"): (S.FIRST_REVIEW, frozenset({"reviewer"})),
    (S.REUPLOAD_REQUESTED, "document_expiry_confirmed"): (
        S.REUPLOAD_REQUESTED,
        frozenset({"reviewer"}),
    ),
    (S.REUPLOAD_REQUESTED, "document_approved"): (S.REUPLOAD_REQUESTED, frozenset({"reviewer"})),
    (S.REUPLOAD_REQUESTED, "document_rejected"): (S.REUPLOAD_REQUESTED, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contacts_requested"): (S.SECOND_REVIEW, frozenset({"reviewer", "system"})),
    (S.SECOND_REVIEW, "sales_data_requested"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contact_removed"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    # Per-contact decisions (demo feedback §3.5): the first-level reviewer, at second review.
    (S.SECOND_REVIEW, "contact_approved"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
    (S.SECOND_REVIEW, "contact_rejected"): (S.SECOND_REVIEW, frozenset({"reviewer"})),
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

# Which review level acts on each reviewer row (demo feedback §3.2, ADR-R2): declared data,
# read by `_check_actor`; no role names in the rules. Rows from the first-review states are
# first level; the rest are final unless listed in FIRST_LEVEL_EVENTS: the contact
# approvals at second review (demo feedback §3.5).
FIRST_LEVEL_EVENTS: frozenset[str] = frozenset({"contact_approved", "contact_rejected"})
DOCUMENT_EVENTS = frozenset({"document_expiry_confirmed", "document_approved", "document_rejected"})
CONTACT_DECISION_EVENTS = frozenset({"contact_approved", "contact_rejected"})
REVIEW_LEVEL: dict[tuple[CaseStatus, str], ReviewLevel] = {
    (from_status, event): (
        "first" if from_status in FIRST_LEVEL_STATES or event in FIRST_LEVEL_EVENTS else "final"
    )
    for (from_status, event), (_to, who) in TABLE.items()
    if "reviewer" in who
}


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
    level = REVIEW_LEVEL.get((case.status, event), "final")
    if queue is None or actor.role != queue.role_for(level) or queue.region not in actor.regions:
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
        if event in DOCUMENT_EVENTS and (
            not get_policy().document_approval or not current_decisions(case)
        ):
            continue
        if event in CONTACT_DECISION_EVENTS and (
            not get_policy().contacts.approval_required
            or not any(c.approval == "pending" for c in case.tenant_contacts)
        ):
            continue
        events.append(event)
    return events


def _approval_blockers(case: Case) -> list[str]:
    blockers = [f"open_request:{r.kind}" for r in case.requests if r.status == "open"]
    policy = get_policy()
    if policy.require_contacts_before_approval:
        by_role = {c.role: c for c in case.tenant_contacts}
        for role in policy.second_level_contacts.required:
            contact = by_role.get(role)
            if contact is None:
                blockers.append(f"missing_contact:{role}")
            elif policy.contacts.approval_required and contact.approval != "approved":
                blockers.append(f"contact_not_approved:{role}")
    return blockers


def approval_blockers(case: Case) -> list[str]:
    """What stops final approval (`approved`)."""
    return _approval_blockers(case)


def first_approval_blockers(case: Case, today: date | None = None) -> list[str]:
    """What stops first-level approval (`approved_first`): the document decisions
    (demo feedback §3.4). Empty with `document_approval: false`."""
    return document_blockers(case, today or clock.now().date())


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
    """Documents to re-upload, with remarks. No `doc_types`: the rejected documents, with
    their rejection remarks as the request's remarks unless others are given (§3.4)."""
    raw = event.payload.get("doc_types")
    rejected = [d for d in current_decisions(case).values() if d.status == "rejected"]
    if (raw is None or raw == []) and rejected:
        raw = [d.doc_type.value for d in rejected]
        remarks = _remarks(event.payload, required=False) or "\n".join(
            f"{document_label(d.doc_type)}: {d.remarks}" for d in rejected if d.remarks
        )
    else:
        remarks = ""
    if not isinstance(raw, list) or not raw:
        raise _invalid("Pick at least one document to re-upload.")
    try:
        doc_types = list(dict.fromkeys(DocType(str(d)) for d in raw))
    except ValueError as exc:
        raise _invalid("Unknown document type.") from exc
    if DocType.SALES_DATA in doc_types:
        raise _invalid("Sales data is requested on its own, not as a re-upload.")
    remarks = remarks or _remarks(event.payload, required=True)
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
        # A new upload is decided again (§3.4, ADR-R4).
        case.document_decisions[doc_type] = DocumentDecision.for_upload(ref)
    _close(request, "fulfilled", now)


def _rejected(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    remarks = _remarks(event.payload, required=True)
    category = event.payload.get("reason_category")
    categories = get_policy().rejection_categories
    if category is not None and category not in categories:
        raise _invalid("Unknown reason category.")
    level: Literal["first", "second"] = "first" if case.status == S.FIRST_REVIEW else "second"
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
    blockers = first_approval_blockers(case, now.date())
    if blockers:
        raise _invalid(f"Can't approve the first level yet: {', '.join(blockers)}.")
    case.decisions.append(
        Decision(
            level="first",
            outcome="approved",
            remarks=_remarks(event.payload, required=False) or None,
            by=actor.id or actor.kind,
            at=now,
        )
    )


# ---- per-document decisions (demo feedback §3.4) ----------------------------------------


def _document_decision(case: Case, event: WorkflowEvent) -> DocumentDecision:
    """The decision this event is about, checked against the current upload."""
    try:
        doc_type = DocType(str(event.payload.get("doc_type") or ""))
    except ValueError as exc:
        raise _invalid("Unknown document type.") from exc
    if doc_type in NON_INTAKE_DOC_TYPES:
        raise _invalid("That document isn't decided at first review.")
    decisions = current_decisions(case)
    decision = decisions.get(doc_type)
    if decision is None:
        raise _invalid("That document isn't on this case.")
    file_id = str(event.payload.get("file_id") or "")
    if not file_id:
        raise _invalid("The document's file id is required.")
    if file_id != decision.file_id:
        raise IllegalTransition(
            "stale_file", "This document has been replaced since you opened it. Reload the case."
        )
    request = case.open_request("reupload")
    if request is not None and doc_type in request.doc_types:
        raise _invalid("A re-upload of this document has been requested: wait for the new file.")
    case.document_decisions = decisions
    return decision


def _not_decided(decision: DocumentDecision) -> None:
    if decision.status != "pending":
        raise _invalid(f"This document is already {decision.status}.")


def _document_expiry_confirmed(
    case: Case, event: WorkflowEvent, actor: Actor, now: datetime
) -> None:
    decision = _document_decision(case, event)
    try:
        expiry = date.fromisoformat(str(event.payload.get("expiry_date") or ""))
    except ValueError as exc:
        raise _invalid("The expiry date must be a date like 2027-03-31.") from exc
    decision.expiry_confirmed = expiry
    decision.expiry_confirmed_by = actor.id or actor.kind
    # An approval can't outlive its expiry: an approved document whose corrected date has
    # passed is decided again.
    if decision.status == "approved" and expiry_status(decision, now.date()) == "expired":
        decision.status = "pending"
        decision.by = None
        decision.at = None


def _document_approved(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    decision = _document_decision(case, event)
    _not_decided(decision)
    if expiry_tracked(decision.doc_type.value):
        status = expiry_status(decision, now.date())
        if status == "expired":
            raise _invalid("This document has expired: reject it and ask for a current one.")
        if status == "unknown":
            raise _invalid("Confirm the document's expiry date before approving it.")
    decision.status = "approved"
    decision.remarks = _remarks(event.payload, required=False) or None
    decision.by = actor.id or actor.kind
    decision.at = now


def _document_rejected(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    decision = _document_decision(case, event)
    _not_decided(decision)
    decision.status = "rejected"
    decision.remarks = _remarks(event.payload, required=True)
    decision.by = actor.id or actor.kind
    decision.at = now


# ---- per-contact decisions (demo feedback §3.5) -----------------------------------------


def _new_contact_id() -> str:
    return f"ct_{uuid.uuid4().hex[:10]}"


def _pending_contact(case: Case, event: WorkflowEvent) -> TenantContact:
    contact_id = str(event.payload.get("contact_id") or "")
    if not contact_id:
        raise _invalid("The contact id is required.")
    contact = case.contact_by_id(contact_id)
    if contact is None:
        raise IllegalTransition(
            "stale_contact", "This contact has changed since you opened it. Reload the case."
        )
    if contact.approval != "pending":
        raise _invalid(f"This contact is already {contact.approval}.")
    return contact


def _contact_approved(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    contact = _pending_contact(case, event)
    contact.approval = "approved"
    contact.approval_remarks = None
    contact.approved_by = actor.id or actor.kind


def _contact_rejected(case: Case, event: WorkflowEvent, actor: Actor, now: datetime) -> None:
    """Rejected: a contacts request for that role opens (or the open one gains the role)."""
    contact = _pending_contact(case, event)
    remarks = _remarks(event.payload, required=True)
    contact.approval = "rejected"
    contact.approval_remarks = remarks
    contact.approved_by = actor.id or actor.kind
    line = f"{CONTACT_ROLE_LABELS[contact.role]}: {remarks}"
    request = case.open_request("contacts")
    if request is None:
        case.requests.append(
            CaseRequest(
                id=f"req_{uuid.uuid4().hex[:10]}",
                kind="contacts",
                roles=[contact.role],
                remarks=line,
                requested_by=actor.id or actor.kind,
                requested_at=now,
            )
        )
    elif request.roles and contact.role not in request.roles:
        request.roles.append(contact.role)
        request.remarks = f"{request.remarks}\n{line}" if request.remarks else line


def _with_approval(case: Case, contact: TenantContact) -> TenantContact:
    """The approval a submitted contact carries (§3.5). Whatever the payload said about
    approval is replaced: an unchanged approved or pending contact keeps its id and state;
    a new, changed or previously rejected one is pending under a new id, except the
    applicant as signatory (the verified primary contact), approved on entry."""
    policy = get_policy()
    previous = next((c for c in case.tenant_contacts if c.role == contact.role), None)
    if (
        previous is not None
        and previous.values() == contact.values()
        and previous.approval != "rejected"
    ):
        contact.contact_id = previous.contact_id
        contact.approval = previous.approval
        contact.approval_remarks = previous.approval_remarks
        contact.approved_by = previous.approved_by
        contact.added_by = previous.added_by
        return contact
    contact.contact_id = _new_contact_id()
    contact.approval_remarks = None
    contact.added_by = "tenant"
    signatory_is_applicant = (
        contact.role == "authorized_signatory"
        and contact.same_as_primary
        and not policy.contacts.applicant_signatory_needs_approval
    )
    if signatory_is_applicant:
        contact.approval = "approved"
        contact.approved_by = "system:verified_primary"
    else:
        contact.approval = "pending"
        contact.approved_by = None
    return contact


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
    case.tenant_contacts = [_with_approval(case, c) for c in contacts]
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
    "document_expiry_confirmed": _document_expiry_confirmed,
    "document_approved": _document_approved,
    "document_rejected": _document_rejected,
    "contact_approved": _contact_approved,
    "contact_rejected": _contact_rejected,
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
