"""Chat streaming endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from app.agent.actions import handle_ui_action
from app.agent.events import SseEvent, run_turn
from app.agent.runtime import AgentRuntime
from app.api.cards import remember_confirm_card_keys
from app.api.deps import get_services, get_session_store, get_settings
from app.api.limiter import limiter
from app.api.schemas import ChatRequestAction, ChatRequestMessage, UiCard
from app.config import Settings
from app.domain.master import load_master_data
from app.services.container import ServiceContainer
from app.sessions import SessionStore

router = APIRouter(prefix="/api/sessions", tags=["chat"])

ChatRequestBody = Annotated[
    ChatRequestMessage | ChatRequestAction,
    Body(discriminator="type"),
]


def _session_rate_limit_key(request: Request) -> str:
    session_id = request.path_params.get("session_id")
    if session_id:
        return f"session:{session_id}"
    return request.client.host if request.client else "unknown"


def _sse(event: SseEvent) -> dict[str, str]:
    return {"event": event["event"], "data": json.dumps(event["data"])}


@router.post("/{session_id}/chat")
@limiter.limit("30/minute", key_func=_session_rate_limit_key)
async def chat_stream(
    request: Request,
    session_id: str,
    body: ChatRequestBody,
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    settings: Settings = Depends(get_settings),
) -> EventSourceResponse:
    graph = request.app.state.graph
    await store.begin_turn(session_id)
    try:
        session = await store.touch(session_id)
    except Exception:
        await store.end_turn(session_id)
        raise

    runtime = AgentRuntime(
        services=services,
        master=load_master_data(),
        settings=settings,
    )

    action_events: list[SseEvent] = []
    if isinstance(body, ChatRequestMessage):
        user_message = HumanMessage(content=body.text)
    else:
        result = await handle_ui_action(body.action, body.payload, session, runtime)
        action_events = result.events
        user_message = result.note

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        try:
            for item in action_events:
                if item["event"] == "ui_card":
                    remember_confirm_card_keys(session, UiCard.model_validate(item["data"]))
                yield _sse(item)
            async for item in run_turn(
                graph,
                session,
                user_message,
                runtime=runtime,
            ):
                yield _sse(item)
        finally:
            await store.end_turn(session_id)

    return EventSourceResponse(event_generator())
