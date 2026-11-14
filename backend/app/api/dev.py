"""Dev and demo tools (L3 §3.4). Mounted only when DEV_TOOLS=true with mock integrations.

- `GET /api/dev/outbox?to=` / `DELETE /api/dev/outbox`: the simulated email and SMS
  outbox behind `/dev/inbox`. It may hold the mock OTP; it is never logged.
- `GET /api/dev/audit/{inquiry_id}`: the redacted audit trail of one inquiry.
- `GET /api/dev/identity/accept/{invitation_id}`: accept a mock Azure AD invitation.
- `GET /api/dev/clock`, `POST /api/dev/clock/advance {hours}`, `POST /api/dev/clock/to-morning`:
  the simulated clock (L5 §3.1); moving it runs a proactive tick.
- `POST /api/dev/proactive/tick`: evaluate the triggers now.
- `GET /api/dev/flow/{id}`: the v2 chart steps a case reached (flow v2 §3.1), by case id,
  reference, inquiry id or session id.
- `POST /api/dev/flow/seed {stage, unit_type?, malls?}`: a case at `submitted`, `qualified`
  or `lead_approved`, built from the real events (flow v2 §3.1).
- `POST /api/dev/reset`: start the demo clean (sessions, cases, outbox, invitations, Yardi
  leads, audit, attention items, uploads, clock).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agent.runtime import AgentRuntime
from app.api.deps import get_master_data, get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.clock import SimulatedClock
from app.config import Settings
from app.domain.master import MasterData
from app.domain.models import FieldKey
from app.domain.sections import BASIC_INFO_KEYS, PROPERTY_KEYS, UNIT_AND_CATEGORY_KEYS
from app.policy.config import get_policy
from app.proactive.engine import TickResult, tick
from app.proactive.notification_policy import quiet_hours_end
from app.services.container import ServiceContainer
from app.sessions import Session, SessionNotFound, SessionStore

router = APIRouter(prefix="/api/dev", tags=["dev"])


# Test runners' "confirm this section" step (flow v2 test plan §4, §6): the cards still showing
# an unconfirmed value of the section, newest first, or a plain "yes" when no card covers it.
# AGENT-DET and Playwright both follow this plan, so one scripted model fits both.
CONFIRM_SECTIONS: dict[str, frozenset[FieldKey]] = {
    "unit_and_category": frozenset(UNIT_AND_CATEGORY_KEYS),
    "basic_info": frozenset(BASIC_INFO_KEYS) | {FieldKey.MOBILE, FieldKey.LANDLINE},
    "property_details": frozenset(PROPERTY_KEYS),
}


class ConfirmPlanOut(BaseModel):
    card_ids: list[str]
    say_yes: bool


def confirm_plan(session: Session, section: str) -> ConfirmPlanOut:
    open_keys = {
        key.value
        for key in CONFIRM_SECTIONS[section]
        if session.draft.fields[key].value not in (None, "", [])
        and not session.draft.fields[key].confirmed
    }
    card_ids: list[str] = []
    for card_id, keys in reversed(list(session.confirm_card_keys.items())):
        if open_keys.intersection(keys):
            card_ids.append(card_id)
            open_keys -= set(keys)
    return ConfirmPlanOut(card_ids=card_ids, say_yes=bool(open_keys))


@router.get("/confirm-plan/{session_id}", response_model=ConfirmPlanOut)
async def get_confirm_plan(
    session_id: str,
    section: Literal["unit_and_category", "basic_info", "property_details"],
    store: SessionStore = Depends(get_session_store),
) -> ConfirmPlanOut:
    try:
        session = await store.get(session_id)
    except SessionNotFound as exc:
        raise ApiError(404, "not_found", "No such session.") from exc
    return confirm_plan(session, section)


@router.get("/outbox")
async def list_outbox(
    to: str | None = Query(default=None),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, list[dict[str, Any]]]:
    return {"messages": services.notifications.messages(to=to)}


@router.delete("/outbox")
async def clear_outbox(
    services: ServiceContainer = Depends(get_services),
) -> dict[str, bool]:
    services.notifications.clear()
    return {"cleared": True}


@router.get("/identity/accept/{invitation_id}", response_class=HTMLResponse)
async def accept_invitation(
    invitation_id: str,
    services: ServiceContainer = Depends(get_services),
) -> HTMLResponse:
    """The mock Azure AD invitation's "Accept invitation" link (L4 §3.2, assumption A3)."""
    invitation = services.identity.accept(invitation_id)
    if invitation is None:
        return HTMLResponse("<p>This invitation isn't valid.</p>", status_code=404)
    # Keep the case's onboarding record in step (the console and the brief show it).
    for case in services.cases.all():
        for recorded in case.onboarding.invitations:
            if recorded.id == invitation.id and recorded.accepted_at is None:
                recorded.accepted_at = invitation.accepted_at
                services.cases.save(case)
    return HTMLResponse(
        "<!doctype html><title>Invitation accepted</title>"
        "<p>Invitation accepted. Your Tenant Central account is ready (simulated Azure AD).</p>"
    )


@router.get("/audit/{inquiry_id}")
async def get_audit(
    inquiry_id: str,
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    return {"inquiry_id": inquiry_id, "events": services.audit.events(inquiry_id)}


class FlowStepOut(BaseModel):
    seq: int | None = None
    at: str | None = None
    node: str | None = None
    outcome: str | None = None
    actor: str | None = None


class FlowOut(BaseModel):
    inquiry_id: str
    reference: str | None
    status: str | None
    path: list[str]
    steps: list[FlowStepOut]


@router.get("/flow/{id_}", response_model=FlowOut)
async def get_flow(
    id_: str,
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
    store: SessionStore = Depends(get_session_store),
) -> FlowOut:
    """Flow v2 §3.1: the chart path, for tests (`expectFlowPath`). Steps recorded before
    submit sit on the session's inquiry; those after on the case (same id once submitted)."""
    from app.workflow.flow import flow_path

    runtime = AgentRuntime(services=services, master=master, settings=settings)
    case = services.cases.get(id_)
    ids: list[str] = []
    if case is None:
        try:
            session = await store.get(id_)
        except SessionNotFound:
            session = None
        if session is not None:
            reference = session.draft.reference
            case = services.cases.get(reference) if reference else None
            ids += [session.origin_id or "", session.inquiry_id or session.id, session.id]
    else:
        ids.append(case.session_id)
        try:
            # A call-centre inquiry (§3.4): its first steps are on the staff chat.
            origin = (await store.get(case.session_id)).origin_id
        except SessionNotFound:
            origin = None
        if origin:
            ids.insert(0, origin)
    if case is not None:
        ids.append(case.id)
    if not ids:
        ids.append(id_)
    steps: list[dict[str, Any]] = []
    for inquiry_id in dict.fromkeys(i for i in ids if i):
        steps += flow_path(runtime, inquiry_id)
    steps.sort(key=lambda s: str(s.get("at") or ""))
    if not steps and case is None:
        raise ApiError(404, "flow_not_found", "No flow steps for that id.")
    return FlowOut(
        inquiry_id=case.id if case else id_,
        reference=case.reference if case else None,
        status=case.status.value if case else None,
        path=[str(s["node"]) for s in steps if s.get("node")],
        steps=[FlowStepOut(**s) for s in steps],
    )


class FlowSeedIn(BaseModel):
    stage: Literal["submitted", "qualified", "lead_approved"]
    unit_type: Literal["store", "office", "media", "specialty"] | None = None
    malls: list[str] | None = None
    # S15 (Playwright): an open inquiry for this CR and mall, the duplicate to warn about.
    cr_number: str | None = Field(default=None, pattern=r"^\d{10}$")


class FlowSeedOut(BaseModel):
    reference: str
    case_id: str
    status: str
    applicant_email: str
    first_reviewer: str | None
    final_reviewer: str | None


@router.post("/flow/seed", response_model=FlowSeedOut)
async def seed_flow(
    body: FlowSeedIn,
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
    store: SessionStore = Depends(get_session_store),
) -> FlowSeedOut:
    from app.demo_seed import reviewer_for, seed_flow_case
    from app.workflow.machine import IllegalTransition

    runtime = AgentRuntime(services=services, master=master, settings=settings)
    try:
        case, email = await seed_flow_case(
            runtime,
            store,
            body.stage,
            unit_type=body.unit_type,
            malls=body.malls,
            cr_number=body.cr_number,
        )
    except (IllegalTransition, RuntimeError, ValueError) as exc:
        raise ApiError(409, "seed_failed", str(exc)) from exc
    return FlowSeedOut(
        reference=case.reference,
        case_id=case.id,
        status=case.status.value,
        applicant_email=email,
        first_reviewer=reviewer_for(runtime, case, "first"),
        final_reviewer=reviewer_for(runtime, case, "final"),
    )


class ClockOut(BaseModel):
    now: datetime
    offset_hours: float
    simulated: bool
    timezone: str


class AdvanceBody(BaseModel):
    hours: float = Field(gt=0, le=24 * 30)


class TickOut(BaseModel):
    clock: ClockOut
    raised: int
    sent: int
    resolved: int


def _clock_out(services: ServiceContainer) -> ClockOut:
    clock = services.clock
    offset = clock.offset if isinstance(clock, SimulatedClock) else timedelta(0)
    return ClockOut(
        now=clock.now(),
        offset_hours=round(offset.total_seconds() / 3600, 2),
        simulated=isinstance(clock, SimulatedClock),
        timezone=get_policy().proactive.quiet_hours.timezone,
    )


def _simulated(services: ServiceContainer) -> SimulatedClock:
    if not isinstance(services.clock, SimulatedClock):
        raise ApiError(409, "clock_not_simulated", "The clock is real time here.")
    return services.clock


async def _tick(services: ServiceContainer, master: MasterData, settings: Settings) -> TickOut:
    result: TickResult = await tick(
        AgentRuntime(services=services, master=master, settings=settings)
    )
    return TickOut(
        clock=_clock_out(services),
        raised=len(result.raised),
        sent=len(result.sent),
        resolved=len(result.resolved),
    )


@router.get("/clock", response_model=ClockOut)
async def get_clock(services: ServiceContainer = Depends(get_services)) -> ClockOut:
    return _clock_out(services)


@router.post("/clock/advance", response_model=TickOut)
async def advance_clock(
    body: AdvanceBody,
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    """Move simulated time forward, then run a proactive tick ("three days later")."""
    _simulated(services).advance(timedelta(hours=body.hours))
    return await _tick(services, master, settings)


@router.post("/clock/to-morning", response_model=TickOut)
async def clock_to_morning(
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    """Move to the end of the next quiet-hours window (08:00 in Riyadh by default)."""
    clock = _simulated(services)
    now = clock.now()
    clock.advance(quiet_hours_end(now, get_policy().proactive) - now)
    return await _tick(services, master, settings)


@router.post("/proactive/tick", response_model=TickOut)
async def run_tick(
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    return await _tick(services, master, settings)


@router.post("/reset")
async def reset_demo(request: Request) -> dict[str, bool]:
    """Delete every demo record and start from the mock world as shipped."""
    await request.app.state.reset_demo()
    return {"reset": True}


class DemoCaseOut(BaseModel):
    """A seeded demo case (day R5) with the reviewers who act on it."""

    key: str
    title: str
    reference: str
    status: str
    first_reviewer: str | None
    final_reviewer: str | None


@router.get("/demo-cases", response_model=list[DemoCaseOut])
async def demo_cases(
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> list[DemoCaseOut]:
    """Cases A, B and C seeded by DEMO_SEED (empty when seeding is off)."""
    from app.demo_seed import list_demo_cases

    runtime = AgentRuntime(services=services, master=master, settings=settings)
    return [DemoCaseOut(**vars(case)) for case in list_demo_cases(runtime)]
