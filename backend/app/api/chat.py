"""Chat streaming endpoint."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from app.agent.actions import cr_answer_result, handle_ui_action
from app.agent.cr_question import CR_TYPED_NOTE, cr_question_active, scrub_cr_numbers
from app.agent.events import SseEvent, run_turn
from app.agent.form_mode import form_mode_cards
from app.agent.redirect import stream_redirect_reply
from app.agent.router import Intent, record_routing_audit, route_message
from app.agent.runtime import AgentRuntime
from app.api.cards import remember_confirm_card_keys, scope_card_data
from app.api.deps import get_services, get_session_store, get_settings
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import ChatRequestAction, ChatRequestMessage, UiCard
from app.audit.draft_changes import record_draft_changes
from app.config import Settings
from app.domain.master import load_master_data
from app.domain.rules import compute_phase
from app.domain.summary import build_draft_summary
from app.services.container import ServiceContainer
from app.sessions import Session, SessionStore, TurnConflict

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
    lease_id = await store.begin_turn(session_id)
    try:
        session = await store.touch(session_id)
    except Exception:
        await store.end_turn(session_id, lease_id)
        raise

    if session.mode == "case":
        graph = request.app.state.case_graph
    elif session.assisted:
        graph = request.app.state.assisted_graph
    else:
        graph = request.app.state.graph

    runtime = AgentRuntime(
        services=services,
        master=load_master_data(),
        settings=settings,
    )

    audit = services.audit
    before_draft = session.draft.model_copy(deep=True)
    action_events: list[SseEvent] = []
    action_quiet = False
    route_decision = None
    user_text: str | None = None
    turn_user_message = HumanMessage(content="")
    user_message_id = f"u_{uuid.uuid4().hex[:10]}"
    if isinstance(body, ChatRequestMessage):
        user_text = body.text
        turn_user_message = HumanMessage(content=body.text)
        cr_typed = False
        if session.mode != "case" and cr_question_active(
            assisted=session.assisted,
            channel=session.channel,
            test_scenario=session.test_scenario,
        ):
            # Demo feedback §3.1: a CR number typed in the public chat is removed before it
            # reaches the transcript, the audit trail or the model, and counts as "Yes".
            user_text, cr_typed = scrub_cr_numbers(body.text)
            turn_user_message = HumanMessage(content=user_text)
        audit.record(
            session.id,
            "user_message",
            actor="user",
            payload={"chars": len(user_text), "message_id": user_message_id},
        )
        if cr_typed:
            answered = cr_answer_result(session, runtime, has_cr=True)
            action_events = answered.events
            turn_user_message = HumanMessage(content=f"{user_text}\n\n{CR_TYPED_NOTE}")
        # Staff (assisted) and case chats skip the intent router: they're on task.
        if not session.form_mode and session.mode != "case" and not session.assisted:
            route_decision = await route_message(user_text, session, runtime)
            record_routing_audit(
                runtime,
                session.id,
                intent=route_decision.intent,
                via=route_decision.via,
                confidence=route_decision.confidence,
            )
    else:
        try:
            result = await handle_ui_action(body.action, body.payload, session, runtime)
        except Exception:
            await store.end_turn(session_id, lease_id)
            raise
        action_events = result.events
        action_quiet = result.quiet
        turn_user_message = result.note
        note = str(result.note.content).removeprefix("[ui_event]").strip()
        audit.record(
            session.id,
            "ui_action",
            actor="user",
            payload={"action": body.action, "outcome": note.split(" ", 1)[0]},
        )
        try:
            await store.save(session)
        except TurnConflict as exc:
            await store.end_turn(session_id, lease_id)
            raise ApiError(
                409,
                "turn_conflict",
                (
                    "This turn couldn't be saved because the inquiry changed "
                    "elsewhere. Please try again."
                ),
            ) from exc

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        nonlocal turn_user_message
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
            if action_quiet:
                # The card already shows the outcome (wrong code, resend, one channel of two
                # verified): no agent turn, so no extra reply (spec §6, quiet card actions).
                yield _sse(
                    SseEvent(event="done", data={"phase": compute_phase(session.draft).value})
                )
                return
            if session.form_mode and user_text is None:
                # Form mode (L3 §3.14): the action is applied; no agent turn runs. The phase
                # decides the next card.
                for card in await form_mode_cards(session, runtime):
                    remember_confirm_card_keys(session, card)
                    item = _scoped(SseEvent(event="ui_card", data=card.model_dump()), session)
                    observe(item)
                    yield _sse(item)
                summary = build_draft_summary(session.draft, runtime.master, [])
                yield _sse(SseEvent(event="draft", data=summary.model_dump()))
                yield _sse(
                    SseEvent(event="done", data={"phase": compute_phase(session.draft).value})
                )
                return
            if user_text is not None and route_decision is not None:
                intent = route_decision.intent
                if intent == Intent.HUMAN_HELP:
                    session.add_message(user_message_id, "user", user_text)
                    result = await handle_ui_action(
                        "request_handoff",
                        {"reason": "user_asked"},
                        session,
                        runtime,
                    )
                    for item in result.events:
                        if item["event"] == "ui_card":
                            remember_confirm_card_keys(session, UiCard.model_validate(item["data"]))
                        item = _scoped(item, session)
                        observe(item)
                        yield _sse(item)
                    note_content = str(result.note.content)
                    turn_user_message = HumanMessage(content=f"{user_text}\n\n{note_content}")
                elif intent in (
                    Intent.GENERAL_INQUIRY,
                    Intent.EXISTING_TENANT_NEW_SPACE,
                    Intent.OFF_TOPIC,
                ):
                    async for item in stream_redirect_reply(intent, user_text, session, runtime):
                        observe(item)
                        yield _sse(item)
                    return
            async for item in run_turn(
                graph,
                session,
                turn_user_message,
                runtime=runtime,
                settings=settings,
                store=store,
                lease_id=lease_id,
            ):
                item = _scoped(item, session)
                observe(item)
                yield _sse(item)
        finally:
            if user_text is not None and not any(
                m.get("id") == user_message_id for m in session.transcript
            ):
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
            try:
                await store.save(session)
            except TurnConflict:
                yield _sse(
                    SseEvent(
                        event="error",
                        data={
                            "code": "turn_conflict",
                            "message": (
                                "This turn couldn't be saved because the inquiry changed "
                                "elsewhere. Please try again."
                            ),
                        },
                    )
                )
            await store.end_turn(session_id, lease_id)

    return EventSourceResponse(event_generator())
