"""Call-centre console API (intake channels §3.2): stands in for the Tenant Admin Platform's
inquiry-creation screen. Mounted only with `CALLCENTRE_CONSOLE=true` and mock integrations.

A mock sign-in picks a staff member (role `customer_care` or `guest_service`); the
frontend sends `X-Staff-Id`. **New inquiry** opens the chat in assisted mode; handoff cases
from the applicant chat open the same inquiry in assisted mode.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel

from app.agent.channels import STAFF_ROLE_LABELS
from app.agent.e2e_scripts import resolve_e2e_scenario
from app.api.cards import build_quick_replies_card
from app.api.deps import get_master_data, get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.api.schemas import AssistantMessage, CreateSessionResponse
from app.api.sessions import resume_payload
from app.config import Settings
from app.domain.master import MasterData
from app.domain.summary import build_draft_summary
from app.services.call_centre import REASON_LABELS
from app.services.container import ServiceContainer
from app.services.reviewers import Reviewer
from app.sessions import SessionNotFound, SessionStore

router = APIRouter(prefix="/api/callcentre", tags=["callcentre"])

STAFF_ROLES = ("customer_care", "guest_service")
NEW_INQUIRY_MESSAGE = (
    "New inquiry for a caller. Start with their CR number — or skip it if they don't have "
    "it to hand."
)


def current_staff(
    x_staff_id: str | None = Header(default=None),
    services: ServiceContainer = Depends(get_services),
) -> Reviewer:
    staff = services.reviewers.get(x_staff_id or "")
    if staff is None or staff.kind != "staff" or staff.role not in STAFF_ROLES:
        raise ApiError(401, "unknown_staff", "Sign in as a call-centre or Guest Service user.")
    return staff


class StaffOut(BaseModel):
    id: str
    name: str
    role: str
    role_label: str


class HandoffOut(BaseModel):
    case_id: str
    inquiry_id: str
    short_ref: str
    reason: str
    reason_label: str
    summary: str
    created_at: str


@router.get("/staff", response_model=list[StaffOut])
async def list_staff(services: ServiceContainer = Depends(get_services)) -> list[StaffOut]:
    """For the mock sign-in picker."""
    return [
        StaffOut(id=s.id, name=s.name, role=s.role, role_label=STAFF_ROLE_LABELS[s.role])
        for s in services.reviewers.all()
        if s.kind == "staff" and s.role in STAFF_ROLES
    ]


@router.post("/inquiries", response_model=CreateSessionResponse)
async def new_inquiry(
    request: Request,
    staff: Reviewer = Depends(current_staff),
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> CreateSessionResponse:
    """A new inquiry in assisted mode (`channel: assisted`, `created_by`: the staff id)."""
    session = await store.create(channel="assisted", created_by=staff.id, staff_id=staff.id)
    if settings.agent_mode == "scripted":
        resolved = resolve_e2e_scenario(request.headers.get("X-Test-Scenario"))
        if resolved:
            session.test_scenario = resolved
            session.script_step = 0
    message = AssistantMessage(id="assisted-1", text=NEW_INQUIRY_MESSAGE)
    card = build_quick_replies_card(
        [
            ("They have a CR", "", "focus_input", "Type the CR number"),
            ("No CR to hand", "Skip the CR for now", None, None),
        ],
        message_id=message.id,
    )
    session.add_message(message.id, "assistant", message.text)
    session.remember_card(card.model_dump())
    services.audit.record(
        session.id, "inquiry_created", actor="staff", payload={"channel": "assisted"}
    )
    store.save(session)
    return CreateSessionResponse(
        session_id=session.id,
        messages=[message],
        cards=[card],
        draft=build_draft_summary(session.draft, master, changed_keys=[]),
    )


@router.get("/handoffs", response_model=list[HandoffOut])
async def list_handoffs(
    _staff: Reviewer = Depends(current_staff),
    services: ServiceContainer = Depends(get_services),
) -> list[HandoffOut]:
    """Open handoff cases from the applicant chat (L3 §3.6), newest first."""
    cases = [c for c in services.call_centre.cases() if c.status == "open"]  # type: ignore[attr-defined]
    cases.sort(key=lambda c: c.created_at, reverse=True)
    return [
        HandoffOut(
            case_id=c.case_id,
            inquiry_id=c.inquiry_id,
            short_ref=c.short_ref,
            reason=c.reason,
            reason_label=REASON_LABELS.get(c.reason, c.reason),
            summary=c.summary,
            created_at=c.created_at,
        )
        for c in cases
    ]


@router.post("/handoffs/{case_id}/open", response_model=CreateSessionResponse)
async def open_handoff(
    case_id: str,
    staff: Reviewer = Depends(current_staff),
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
) -> CreateSessionResponse:
    """Continue the same inquiry in assisted mode, with a summary for the executive."""
    case = next((c for c in services.call_centre.cases() if c.case_id == case_id), None)  # type: ignore[attr-defined]
    if case is None:
        raise ApiError(404, "case_not_found", "No such handoff case.")
    try:
        session = await store.revive(case.inquiry_id)
    except SessionNotFound as exc:
        raise ApiError(404, "inquiry_not_found", "That inquiry is no longer available.") from exc
    session.staff_id = staff.id
    message_id = f"handoff-{len(session.transcript) + 1}"
    session.add_message(
        message_id,
        "assistant",
        f"Picked up from the applicant's chat ({case.short_ref}). {case.summary} "
        "Carry on with the caller from here; anything you add is marked as entered by staff.",
    )
    services.audit.record(
        session.id, "inquiry_created", actor="staff", payload={"channel": "assisted"}
    )
    store.save(session)
    return resume_payload(session, master)
