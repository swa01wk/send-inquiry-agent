"""Stream a reviewer-assistant turn as SSE events (L4 §3.6)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent.events import SseEvent, _audit_turn, _new_message_id, _ReplyTracker, _text_of
from app.agent.model import ModelUnavailable
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState, initial_agent_state
from app.domain.rules import compute_phase
from app.workflow.models import Case

logger = logging.getLogger(__name__)

_AGENT_NODE = "agent"


def reviewer_thread_id(case_id: str, reviewer_id: str) -> str:
    return f"review:{case_id}:{reviewer_id}"


def _graph_config(
    *,
    thread_id: str,
    runtime: AgentRuntime,
    bound_model: Any | None = None,
) -> RunnableConfig:
    configurable: dict[str, object] = {"thread_id": thread_id, "runtime": runtime}
    if bound_model is not None:
        configurable["bound_chat_model"] = bound_model
    return {"configurable": configurable}


async def run_reviewer_turn(
    graph: Any,
    *,
    case: Case,
    reviewer_id: str,
    text: str,
    runtime: AgentRuntime,
    bound_model: Any | None = None,
) -> AsyncIterator[SseEvent]:
    thread_id = reviewer_thread_id(case.id, reviewer_id)
    phase = compute_phase(case.draft).value
    state: AgentState = initial_agent_state(
        session_id=thread_id,
        draft=case.draft,
        phase=phase,
    )
    state["case_id"] = case.id
    state["messages"] = [HumanMessage(content=text)]

    config = _graph_config(thread_id=thread_id, runtime=runtime, bound_model=bound_model)
    before = await graph.aget_state(config)
    prior_count = len((before.values or {}).get("messages", []))

    runtime.services.audit.record(
        case.id,
        "user_message",
        actor="reviewer",
        payload={"chars": len(text), "message_id": f"u_{uuid.uuid4().hex[:10]}"},
    )

    replies = _ReplyTracker()
    pending_cards: list[SseEvent] = []
    retractions = 0
    final_messages: list[BaseMessage] = []

    try:
        async for mode, chunk in graph.astream(
            state,
            config=config,
            stream_mode=["messages", "custom"],
        ):
            if mode == "custom":
                if not isinstance(chunk, dict):
                    continue
                event_type = chunk.get("type")
                data = chunk.get("data")
                if event_type == "ui_card" and isinstance(data, dict):
                    pending_cards.append(SseEvent(event="ui_card", data=data))
                elif event_type == "retract_reply":
                    removed = replies.retract_latest()
                    if removed is not None:
                        retractions += 1
                        yield SseEvent(event="message_remove", data={"message_id": removed})
                continue

            if mode != "messages":
                continue
            message_chunk, meta = chunk
            if not isinstance(meta, dict) or meta.get("langgraph_node") != _AGENT_NODE:
                continue
            if not isinstance(message_chunk, AIMessage):
                continue

            key = replies.key_for(meta)
            replies.note_call(key)
            is_chunk = isinstance(message_chunk, AIMessageChunk)
            if not is_chunk and replies.was_chunked(key):
                continue
            token_text = _text_of(message_chunk)
            if not token_text:
                continue
            if is_chunk:
                replies.mark_chunked(key)
            yield SseEvent(
                event="token",
                data={"message_id": replies.id_for(key), "text": token_text},
            )

        snapshot = await graph.aget_state(config)
        final = cast(AgentState, snapshot.values)
        final_messages = list(final.get("messages", []))
        _audit_turn(runtime, case.id, final_messages[prior_count:], retractions)

        if replies.last_text_id is None:
            for message in reversed(final_messages):
                if isinstance(message, AIMessage) and _text_of(message):
                    reply_id = _new_message_id()
                    replies.last_text_id = reply_id
                    yield SseEvent(
                        event="token",
                        data={"message_id": reply_id, "text": _text_of(message)},
                    )
                    break

        audit = runtime.services.audit
        for card_event in pending_cards:
            if card_event["data"].get("message_id") is None and replies.last_text_id:
                card_event["data"]["message_id"] = replies.last_text_id
            payload = card_event["data"].get("payload") or {}
            if card_event["data"].get("card_type") == "reviewer_suggestion":
                audit.record(
                    case.id,
                    "assistant_suggestion",
                    actor="agent",
                    payload={"kind": payload.get("kind"), "action": payload.get("action")},
                )
            audit.record(
                case.id,
                "card_shown",
                actor="agent",
                payload={
                    "card_type": card_event["data"].get("card_type"),
                    "card_id": card_event["data"].get("card_id"),
                },
            )
            yield card_event

        done_phase = str(final.get("phase", phase))
        yield SseEvent(event="done", data={"phase": done_phase})

    except ModelUnavailable:
        logger.exception("reviewer assistant model unavailable")
        yield SseEvent(
            event="error",
            data={
                "code": "agent_error",
                "message": "The assistant is not available right now. Please try again.",
            },
        )
    except Exception:
        logger.exception("reviewer assistant turn failed")
        yield SseEvent(
            event="error",
            data={
                "code": "agent_error",
                "message": "Sorry, something went wrong on our side. Please try again.",
            },
        )
