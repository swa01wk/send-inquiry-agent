"""Reviewer console API (L4 §3.3): stands in for the Tenant Admin Platform.

Mounted only with `REVIEWER_CONSOLE=true` and `INTEGRATIONS=mock`. A mock sign-in picks a
reviewer; the frontend then sends `X-Reviewer-Id` on every call. Every action is one
state-machine event with the reviewer as actor; the machine (not this API) checks the
reviewer's queue. A case outside the reviewer's queue is a 404, as if it didn't exist.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app import clock
from app.agent.events import SseEvent
from app.agent.reviewer_events import run_reviewer_turn
from app.agent.runtime import AgentRuntime
from app.api.deps import get_master_data, get_services
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.config import Settings
from app.domain.case_brief import STAGE_LABELS, CaseBrief, build_case_brief, waiting_on
from app.domain.fields import DOCUMENT_LABELS
from app.domain.master import MasterData
from app.domain.models import FieldKey
from app.policy.config import get_policy
from app.proactive.engine import ProactiveError, hours_between
from app.proactive.engine import approve as proactive_approve
from app.proactive.engine import dismiss as proactive_dismiss
from app.proactive.models import RECOMMENDED, TRIGGER_LABELS, AttentionItem
from app.services.container import ServiceContainer
from app.services.reviewers import Reviewer
from app.services.status import REQUEST_LABELS
from app.workflow.machine import IllegalTransition, approval_blockers, legal_events
from app.workflow.models import Case, WorkflowEvent
from app.workflow.service import apply_event

router = APIRouter(prefix="/api/review", tags=["review"])

# Console action → state-machine event (1:1, L4 §3.3).
ACTIONS: dict[str, str] = {
    "request_reupload": "reupload_requested",
    "reject": "rejected",
    "approve_first": "approved_first",
    "request_contacts": "contacts_requested",
    "request_sales_data": "sales_data_requested",
    "withdraw_request": "request_withdrawn",
    "relink_company": "company_relinked",
    "relink_brand": "brand_relinked",
    "remove_contact": "contact_removed",
    "approve": "approved",
}
EVENT_TO_ACTION = {event: action for action, event in ACTIONS.items()}
_STATUS_FOR_ERROR = {"not_in_queue": 403, "not_allowed": 403, "invalid_payload": 400}


def current_reviewer(
    x_reviewer_id: str | None = Header(default=None),
    services: ServiceContainer = Depends(get_services),
) -> Reviewer:
    reviewer = services.reviewers.get(x_reviewer_id or "")
    if reviewer is None:
        raise ApiError(401, "unknown_reviewer", "Sign in as a reviewer first.")
    return reviewer


def _in_queue(case: Case, reviewer: Reviewer) -> bool:
    queue = case.review_queue
    return (
        queue is not None
        and reviewer.kind == "reviewer"
        and reviewer.role == queue.role
        and queue.region in reviewer.regions
    )


def _case_for(services: ServiceContainer, case_id: str, reviewer: Reviewer) -> Case:
    case = services.cases.get(case_id)
    if case is None or not _in_queue(case, reviewer):
        raise ApiError(404, "case_not_found", "No such case in your queues.")
    return case


class ReviewerOut(BaseModel):
    id: str
    name: str
    role: str
    regions: list[str]
    manager: bool


class QueueItem(BaseModel):
    reference: str
    brand: str | None
    company: str | None
    mall: str | None
    product_line: str | None
    region: str | None
    status: str
    stage_label: str
    waiting_on: str
    age_days: float
    last_change: datetime
    open_requests: list[str]
    possible_duplicate: bool = False
    follow_on_of: str | None = None
    needs_operations: bool = False


class TimelineEntry(BaseModel):
    at: datetime
    actor: str
    type: str
    summary: str


class CaseDetail(BaseModel):
    brief: CaseBrief
    timeline: list[TimelineEntry]
    legal_actions: list[str]
    approval_blockers: list[str]
    rejection_categories: list[str]
    reupload_doc_types: list[dict[str, str]]


class YardiCompanyOut(BaseModel):
    id: str
    name: str


class YardiBrandOut(BaseModel):
    id: str
    name: str
    source: str


class ActionRequest(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _sse(event: SseEvent) -> dict[str, str]:
    return {"event": event["event"], "data": json.dumps(event["data"])}


def _queue_item(case: Case, master: MasterData, now: datetime) -> QueueItem:
    fields = case.draft.fields
    malls = fields[FieldKey.MALLS].value or []
    return QueueItem(
        reference=case.reference,
        brand=fields[FieldKey.BRAND_NAME_EN].value,
        company=fields[FieldKey.COMPANY_NAME].value,
        mall=master.label_for("malls", malls[0]) if malls else None,
        product_line=fields[FieldKey.UNIT_TYPE].value,
        region=case.review_queue.region if case.review_queue else None,
        status=case.status.value,
        stage_label=STAGE_LABELS.get(case.status.value, case.status.value),
        waiting_on=waiting_on(case),
        age_days=round((now - case.submitted_at).total_seconds() / 86400, 2),
        last_change=case.last_change,
        open_requests=[r.kind for r in case.requests if r.status == "open"],
        follow_on_of=case.draft.follow_on_of,
        needs_operations=case.yardi.needs_operations,
    )


_EVENT_SUMMARIES: dict[str, str] = {
    "inquiry_created": "Inquiry started",
    "user_message": "Applicant sent a message",
    "ui_action": "Applicant used a card",
    "field_written": "Field saved",
    "field_confirmed": "Fields confirmed",
    "verification_sent": "Verification sent",
    "verification_result": "Verification result",
    "document_added": "Document uploaded",
    "document_removed": "Document removed",
    "submit_attempt": "Submit pressed",
    "submit_result": "Submit result",
    "notification_sent": "Notification sent",
    "handoff_created": "Handoff to the call centre",
    "follow_on_started": "Follow-on inquiry started",
    "form_mode_entered": "Assistant unavailable: form mode",
    "form_mode_left": "Assistant back",
    "case_created": "Case created",
    "effect_run": "Effect",
    "guard_verdict": "Guard retracted a reply",
    "tool_called": "Tool called",
    "card_shown": "Card shown",
}
_HIDDEN = {"tool_called", "card_shown", "routing_decision"}


def _summary(event: dict[str, Any]) -> str:
    payload = event.get("payload") or {}
    kind = event["type"]
    if kind == "case_transition":
        outcome = payload.get("outcome")
        name = str(payload.get("event", "")).replace("_", " ")
        if outcome == "applied":
            return f"{name.capitalize()} → {payload.get('to_status')}"
        return f"{name.capitalize()} refused ({outcome})"
    base = _EVENT_SUMMARIES.get(kind, kind.replace("_", " ").capitalize())
    detail = (
        payload.get("key")
        or payload.get("action")
        or payload.get("template")
        or payload.get("effect")
        or payload.get("doc_type")
        or payload.get("outcome")
        or payload.get("reason")
    )
    return f"{base}: {detail}" if detail else base


def _timeline(services: ServiceContainer, case: Case) -> list[TimelineEntry]:
    keys = [case.session_id, case.id, *([case.case_session_id] if case.case_session_id else [])]
    entries: list[TimelineEntry] = []
    for key in dict.fromkeys(keys):
        for event in services.audit.events(key):
            if event["type"] in _HIDDEN:
                continue
            payload = event.get("payload") or {}
            actor = str(event.get("actor", "system"))
            if event["type"] == "case_transition" and payload.get("by"):
                actor = f"{actor} ({payload['by']})" if actor in ("reviewer", "staff") else actor
            entries.append(
                TimelineEntry(
                    at=datetime.fromisoformat(event["at"]),
                    actor=actor,
                    type=event["type"],
                    summary=_summary(event),
                )
            )
    return sorted(entries, key=lambda e: e.at)


def _detail(
    services: ServiceContainer, case: Case, reviewer: Reviewer, master: MasterData
) -> CaseDetail:
    return CaseDetail(
        brief=build_case_brief(case, master),
        timeline=_timeline(services, case),
        legal_actions=[
            EVENT_TO_ACTION[e] for e in legal_events(case, reviewer.actor()) if e in EVENT_TO_ACTION
        ],
        approval_blockers=approval_blockers(case),
        rejection_categories=list(get_policy().rejection_categories),
        reupload_doc_types=[{"doc_type": d.value, "label": label} for d, label in DOCUMENT_LABELS],
    )


@router.get("/reviewers", response_model=list[ReviewerOut])
async def list_reviewers(services: ServiceContainer = Depends(get_services)) -> list[ReviewerOut]:
    """For the mock sign-in picker."""
    return [
        ReviewerOut(id=r.id, name=r.name, role=r.role, regions=r.regions, manager=r.manager)
        for r in services.reviewers.all()
        if r.kind == "reviewer"
    ]


@router.get("/me", response_model=ReviewerOut)
async def me(reviewer: Reviewer = Depends(current_reviewer)) -> ReviewerOut:
    return ReviewerOut(
        id=reviewer.id,
        name=reviewer.name,
        role=reviewer.role,
        regions=reviewer.regions,
        manager=reviewer.manager,
    )


@router.get("/cases", response_model=list[QueueItem])
async def list_cases(
    waiting_on_filter: str | None = Query(default=None, alias="waiting_on"),
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
) -> list[QueueItem]:
    now = clock.now()
    items = [
        _queue_item(case, master, now) for case in services.cases.all() if _in_queue(case, reviewer)
    ]
    if waiting_on_filter:
        items = [i for i in items if i.waiting_on == waiting_on_filter]
    return sorted(items, key=lambda i: i.last_change, reverse=True)


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(
    case_id: str,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
) -> CaseDetail:
    return _detail(services, _case_for(services, case_id, reviewer), reviewer, master)


@router.get("/yardi/companies", response_model=list[YardiCompanyOut])
async def search_yardi_companies(
    q: str = Query(default="", max_length=120),
    _reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
) -> list[YardiCompanyOut]:
    """Active Yardi companies by the first word of the name: the options for `relink_company`."""
    return [YardiCompanyOut(id=c.id, name=c.name) for c in services.yardi.search_companies(q)]


@router.get("/yardi/companies/{company_id}/brands", response_model=list[YardiBrandOut])
async def yardi_brands(
    company_id: str,
    _reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
) -> list[YardiBrandOut]:
    """That company's brands (previous leases and proposals): the options for `relink_brand`."""
    if services.yardi.company(company_id) is None:
        raise ApiError(404, "company_not_found", "Unknown Yardi company.")
    return [
        YardiBrandOut(id=b.id, name=b.name, source=b.source)
        for b in services.yardi.brands_for_company(company_id)
    ]


@router.get("/cases/{case_id}/documents/{file_id}")
async def download_document(
    case_id: str,
    file_id: str,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
) -> FileResponse:
    case = _case_for(services, case_id, reviewer)
    refs = [*case.draft.documents.values(), *case.document_history]
    if case.sales_data:
        refs.append(case.sales_data)
    ref = next((r for r in refs if r.file_id == file_id), None)
    sessions = [case.session_id, *([case.case_session_id] if case.case_session_id else [])]
    path = services.storage.path_for(sessions, file_id) if ref else None  # type: ignore[attr-defined]
    if ref is None or path is None:
        raise ApiError(404, "document_not_found", "That document isn't on this case.")
    return FileResponse(path, filename=ref.file_name)


@router.post("/cases/{case_id}/actions", response_model=CaseDetail)
async def act(
    case_id: str,
    body: ActionRequest,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> CaseDetail:
    case = _case_for(services, case_id, reviewer)
    event_name = ACTIONS.get(body.action)
    if event_name is None:
        raise ApiError(400, "unknown_action", f"Unknown action: {body.action}.")
    payload = dict(body.payload)
    if event_name in ("company_relinked", "brand_relinked"):
        _check_yardi_ids(services, case, event_name, payload)
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    try:
        updated = await apply_event(
            runtime, case.id, WorkflowEvent(name=event_name, payload=payload), reviewer.actor()
        )
    except IllegalTransition as exc:
        status = _STATUS_FOR_ERROR.get(exc.code, 409)
        raise ApiError(status, exc.code, exc.message) from exc
    return _detail(services, updated, reviewer, master)


def _check_yardi_ids(
    services: ServiceContainer, case: Case, event_name: str, payload: dict[str, Any]
) -> None:
    """The ids exist; a brand belongs to the linked company (M0 §6 guard)."""
    yardi = services.yardi
    if event_name == "company_relinked":
        if yardi.company(str(payload.get("company_id", ""))) is None:
            raise ApiError(400, "invalid_payload", "Unknown Yardi company.")
        return
    company_id = case.yardi.company_id
    brands = yardi.brands_for_company(company_id) if company_id else []
    if not any(b.id == payload.get("brand_id") for b in brands):
        raise ApiError(400, "invalid_payload", "That brand isn't one of the linked company's.")


@router.post("/cases/{case_id}/assistant")
async def assistant_chat(
    request: Request,
    case_id: str,
    body: AssistantRequest,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> EventSourceResponse:
    """Reviewer-assistant chat for one case (SSE: token, ui_card, done)."""
    case = _case_for(services, case_id, reviewer)
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    graph = request.app.state.reviewer_graph

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        async for item in run_reviewer_turn(
            graph,
            case=case,
            reviewer_id=reviewer.id,
            text=body.text,
            runtime=runtime,
        ):
            yield _sse(item)

    return EventSourceResponse(event_generator())


# ---- Needs attention (L5 §3.4, thin) --------------------------------------------------


class AttentionOut(BaseModel):
    id: str
    trigger: str
    label: str
    recommended: str
    reference: str
    brand: str | None
    mall: str | None
    stage_label: str
    status: str
    audience: str
    tier: int
    age_hours: float
    threshold_hours: int
    request_kind: str | None
    request_label: str | None
    text: str | None
    raised_at: datetime
    send_after: datetime | None
    sent_at: datetime | None
    dismissed_reason: str | None


class AttentionCounts(BaseModel):
    open: int
    raised: int
    sent: int
    dismissed: dict[str, int]


class AttentionList(BaseModel):
    items: list[AttentionOut]
    counts: AttentionCounts
    dismiss_reasons: list[str]


class ApproveBody(BaseModel):
    text: str | None = None


class DismissBody(BaseModel):
    reason: str


ACTIONABLE = ("open", "awaiting_approval", "held")


def _sees(item: AttentionItem, case: Case | None, reviewer: Reviewer) -> bool:
    if case is None:
        return False
    if item.audience == "manager":
        return reviewer.manager and reviewer.role == item.queue_role
    return _in_queue(case, reviewer)


def _attention_out(item: AttentionItem, case: Case, master: MasterData) -> AttentionOut:
    fields = case.draft.fields
    malls = fields[FieldKey.MALLS].value or []
    return AttentionOut(
        id=item.id,
        trigger=item.trigger,
        label=TRIGGER_LABELS[item.trigger],
        recommended=RECOMMENDED[item.trigger],
        reference=case.reference,
        brand=fields[FieldKey.BRAND_NAME_EN].value,
        mall=master.label_for("malls", malls[0]) if malls else None,
        stage_label=STAGE_LABELS.get(item.stage, item.stage),
        status=item.status,
        audience=item.audience,
        tier=item.tier,
        age_hours=round(hours_between(item.since, clock.now()), 1),
        threshold_hours=item.threshold_hours,
        request_kind=item.request_kind,
        request_label=REQUEST_LABELS.get(item.request_kind) if item.request_kind else None,
        text=item.text,
        raised_at=item.raised_at,
        send_after=item.send_after,
        sent_at=item.sent_at,
        dismissed_reason=item.dismissed_reason,
    )


def _visible_item(services: ServiceContainer, item_id: str, reviewer: Reviewer) -> AttentionItem:
    item = services.attention.get(item_id)
    case = services.cases.get(item.case_id) if item else None
    if item is None or not _sees(item, case, reviewer):
        raise ApiError(404, "item_not_found", "No such item in your queues.")
    return item


@router.get("/attention", response_model=AttentionList)
async def list_attention(
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
) -> AttentionList:
    """Items for the reviewer's queues (escalations for managers), most urgent first."""
    visible: list[tuple[AttentionItem, Case]] = []
    for item in services.attention.all():
        case = services.cases.get(item.case_id)
        if case is not None and _sees(item, case, reviewer):
            visible.append((item, case))
    now = clock.now()
    actionable = [(i, c) for i, c in visible if i.status in ACTIONABLE]
    actionable.sort(
        key=lambda pair: (
            pair[0].trigger != "escalation",
            -hours_between(pair[0].since, now) / pair[0].threshold_hours,
        )
    )
    dismissed: dict[str, int] = {}
    for item, _case in visible:
        if item.status == "dismissed" and item.dismissed_reason:
            dismissed[item.dismissed_reason] = dismissed.get(item.dismissed_reason, 0) + 1
    return AttentionList(
        items=[_attention_out(i, c, master) for i, c in actionable],
        counts=AttentionCounts(
            open=len(actionable),
            raised=len(visible),
            sent=sum(1 for i, _c in visible if i.status == "sent"),
            dismissed=dismissed,
        ),
        dismiss_reasons=list(get_policy().proactive.dismiss_reasons),
    )


def _runtime(services: ServiceContainer, master: MasterData, settings: Settings) -> AgentRuntime:
    return AgentRuntime(services=services, master=master, settings=settings)


@router.post("/attention/{item_id}/approve", response_model=AttentionOut)
async def approve_attention(
    item_id: str,
    body: ApproveBody,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> AttentionOut:
    """Approve a drafted reminder (optionally edited). It sends now, or is held for quiet
    hours or the per-case throttle."""
    _visible_item(services, item_id, reviewer)
    try:
        item = await proactive_approve(
            _runtime(services, master, settings), item_id, by=reviewer.id, text=body.text
        )
    except ProactiveError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from exc
    case = services.cases.get(item.case_id)
    assert case is not None
    return _attention_out(item, case, master)


@router.post("/attention/{item_id}/dismiss", response_model=AttentionOut)
async def dismiss_attention(
    item_id: str,
    body: DismissBody,
    reviewer: Reviewer = Depends(current_reviewer),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> AttentionOut:
    _visible_item(services, item_id, reviewer)
    try:
        item = proactive_dismiss(
            _runtime(services, master, settings), item_id, by=reviewer.id, reason=body.reason
        )
    except ProactiveError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from exc
    case = services.cases.get(item.case_id)
    assert case is not None
    return _attention_out(item, case, master)
