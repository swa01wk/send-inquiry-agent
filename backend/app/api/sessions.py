"""Session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.cards import (
    WELCOME_MESSAGE_1,
    WELCOME_MESSAGE_2,
    build_welcome_quick_replies_card,
)
from app.api.deps import get_master_data, get_session_store, get_settings
from app.api.limiter import limiter
from app.api.schemas import AssistantMessage, CreateSessionResponse
from app.config import Settings
from app.domain.master import MasterData
from app.domain.summary import DraftSummary, build_draft_summary
from app.sessions import SessionStore

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

WELCOME_MSG_ID_1 = "welcome-1"
WELCOME_MSG_ID_2 = "welcome-2"


@router.post("", response_model=CreateSessionResponse)
@limiter.limit("60/minute")
async def create_session(
    request: Request,
    store: SessionStore = Depends(get_session_store),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings),
) -> CreateSessionResponse:
    session = await store.create()
    if settings.agent_mode == "scripted":
        scenario = request.headers.get("X-Test-Scenario")
        if scenario:
            session.test_scenario = scenario.strip()
            session.script_step = 0
    messages = [
        AssistantMessage(id=WELCOME_MSG_ID_1, text=WELCOME_MESSAGE_1),
        AssistantMessage(id=WELCOME_MSG_ID_2, text=WELCOME_MESSAGE_2),
    ]
    cards = [build_welcome_quick_replies_card(message_id=WELCOME_MSG_ID_2)]
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return CreateSessionResponse(
        session_id=session.id,
        messages=messages,
        cards=cards,
        draft=draft,
    )


@router.get("/{session_id}/draft", response_model=DraftSummary)
@limiter.limit("60/minute")
async def get_draft(
    request: Request,
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    master: MasterData = Depends(get_master_data),
) -> DraftSummary:
    session = await store.touch(session_id)
    return build_draft_summary(session.draft, master, changed_keys=[])
