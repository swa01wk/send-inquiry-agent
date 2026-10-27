"""Chat streaming endpoint."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from app.agent.actions import handle_ui_action
from app.agent.events import SseEvent, run_turn
from app.agent.runtime import AgentRuntime
from app.api.cards import remember_confirm_card_keys, scope_card_data
from app.api.deps import get_services, get_session_store, get_settings
from app.api.limiter import limiter
from app.api.schemas import ChatRequestAction, ChatRequestMessage, UiCard
from app.audit.draft_changes import record_draft_changes
from app.config import Settings
from app.domain.master import load_master_data
from app.services.container import ServiceContainer
from app.sessions import Session, SessionStore

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


def _scoped(event: SseEvent, session: Session) -> SseEvent:
    """Card ids carry the inquiry's number after a follow-on (L3 §3.11)."""
    if event["event"] != "ui_card":
        return event
    return SseEvent(event="ui_card", data=scope_card_data(event["data"], session.inquiry_seq))


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

    audit = services.audit
    before_draft = session.draft.model_copy(deep=True)
    action_events: list[SseEvent] = []
    user_text: str | None = None
    user_message_id = f"u_{uuid.uuid4().hex[:10]}"
    if isinstance(body, ChatRequestMessage):
        user_text = body.text
        user_message = HumanMessage(content=body.text)
        audit.record(
            session.id,
            "user_message",
            actor="user",
            payload={"chars": len(body.text), "message_id": user_message_id},
        )
    else:
        try:
            result = await handle_ui_action(body.action, body.payload, session, runtime)
        except Exception:
            await store.end_turn(session_id)
            raise
        action_events = result.events
        user_message = result.note
        note = str(result.note.content).removeprefix("[ui_event]").strip()
        audit.record(
            session.id,
            "ui_action",
            actor="user",
            payload={"action": body.action, "outcome": note.split(" ", 1)[0]},
        )
        store.save(session)

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        replies: dict[str, str] = {}
        removed: set[str] = set()

        def observe(item: SseEvent) -> None:
            data = item["data"]
            if item["event"] == "token":
                message_id = str(data.get("message_id", ""))
                replies[message_id] = replies.get(message_id, "") + str(data.get("text", ""))
            elif item["event"] == "message_remove":
                removed.add(str(data.get("message_id", "")))
            elif item["event"] == "ui_card":
                session.remember_card(data)
                audit.record(
                    session.id,
                    "card_shown",
                    actor="agent",
                    payload={"card_type": data.get("card_type"), "card_id": data.get("card_id")},
                )

        try:
            for item in action_events:
                if item["event"] == "ui_card":
                    remember_confirm_card_keys(session, UiCard.model_validate(item["data"]))
                item = _scoped(item, session)
                observe(item)
                yield _sse(item)
            async for item in run_turn(
                graph,
                session,
                user_message,
                runtime=runtime,
                settings=settings,
            ):
                item = _scoped(item, session)
                observe(item)
                yield _sse(item)
        finally:
            if user_text is not None:
                session.add_message(user_message_id, "user", user_text)
            for message_id, text in replies.items():
                if message_id not in removed and text.strip():
                    session.add_message(message_id, "assistant", text)
            record_draft_changes(
                audit,
                session.id,
                before_draft,
                session.draft,
                actor="user" if user_text is None else "agent",
                via="card" if user_text is None else "agent",
            )
            store.save(session)
            await store.end_turn(session_id)

    return EventSourceResponse(event_generator())
