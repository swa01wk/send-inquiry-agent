"""Session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agent.e2e_scripts import resolve_e2e_scenario
from app.api.cards import (
    WELCOME_MESSAGE_1,
    WELCOME_MESSAGE_2,
    build_welcome_quick_replies_card,
)
from app.api.deps import get_master_data, get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import AssistantMessage, CreateSessionResponse, ResumeRequest, UiCard
from app.config import Settings, get_settings
from app.domain.master import MasterData
from app.domain.summary import DraftSummary, build_draft_summary
from app.gateway import FaultSpecError
from app.security import tokens
from app.services.container import ServiceContainer
from app.sessions import Session, SessionNotFound, SessionStore

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

WELCOME_MSG_ID_1 = "welcome-1"
WELCOME_MSG_ID_2 = "welcome-2"


@router.post("", response_model=CreateSessionResponse)
@limiter.limit(get_settings().rate_limit_ip)
async def create_session(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
    services: ServiceContainer = Depends(get_services),
) -> CreateSessionResponse:
    session = await store.create()
    if settings.agent_mode == "scripted":
        resolved = resolve_e2e_scenario(request.headers.get("X-Test-Scenario"))
        if resolved:
            session.test_scenario = resolved
            session.script_step = 0
        # Per-session fault injection for tests (L3 §3.1); ignored outside scripted mode.
        try:
            services.gateway.set_session_faults(session.id, request.headers.get("X-Mock-Faults"))
        except FaultSpecError as exc:
            raise ApiError(400, "bad_mock_faults", str(exc)) from exc
    messages = [
        AssistantMessage(id=WELCOME_MSG_ID_1, text=WELCOME_MESSAGE_1),
        AssistantMessage(id=WELCOME_MSG_ID_2, text=WELCOME_MESSAGE_2),
    ]
    cards = [build_welcome_quick_replies_card(message_id=WELCOME_MSG_ID_2)]
    for message in messages:
        session.add_message(message.id, "assistant", message.text)
    for card in cards:
        session.remember_card(card.model_dump())
    services.audit.record(
        session.id, "inquiry_created", actor="user", payload={"channel": "self_service"}
    )
    store.save(session)
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return CreateSessionResponse(
        session_id=session.id,
        messages=messages,
        cards=cards,
        draft=draft,
    )


@router.get("/{session_id}/draft", response_model=DraftSummary)
@limiter.limit(get_settings().rate_limit_ip)
async def get_draft(
    request: Request,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    master: MasterData = Depends(get_master_data),
) -> DraftSummary:
    session = await store.touch(session_id)
    return build_draft_summary(session.draft, master, changed_keys=[])


RESUME_MESSAGES = 20


def resume_payload(session: Session, master: MasterData) -> CreateSessionResponse:
    """What the chat needs to render exactly where the user left off."""
    messages = [AssistantMessage.model_validate(m) for m in session.transcript[-RESUME_MESSAGES:]]
    cards = [UiCard.model_validate(card) for card in session.cards.values()]
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return CreateSessionResponse(session_id=session.id, messages=messages, cards=cards, draft=draft)


@router.post("/resume", response_model=CreateSessionResponse)
@limiter.limit(get_settings().rate_limit_ip)
async def resume_session(
    request: Request,
    body: ResumeRequest,
    store: SessionStore = Depends(get_session_store),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> CreateSessionResponse:
    """Reopen an inquiry from a signed `resume` link (L3 §3.2), on any device."""
    try:
        claims = tokens.read(settings.token_secret, body.token, "resume")
    except tokens.TokenError as exc:
        message = (
            "This link has expired. Start the inquiry again or ask for a new link."
            if exc.code == "token_expired"
            else "This link isn't valid."
        )
        raise ApiError(400, exc.code, message) from exc
    try:
        session = await store.revive(claims.subject)
    except SessionNotFound as exc:
        raise ApiError(404, "inquiry_not_found", "We couldn't find that inquiry.") from exc
    store.save(session)
    return resume_payload(session, master)
