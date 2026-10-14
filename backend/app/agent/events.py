"""Stream a single agent turn as SSE-shaped events."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict, cast

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState, initial_agent_state
from app.domain.rules import compute_phase
from app.observability.turn_log import TurnTimer, log_chat_turn
from app.sessions import Session

logger = logging.getLogger(__name__)

EventType = Literal["token", "ui_card", "draft", "done", "error"]


class SseEvent(TypedDict):
    event: EventType
    data: dict[str, Any]


def _graph_config(session: Session, runtime: AgentRuntime) -> RunnableConfig:
    return {
        "configurable": {
            "thread_id": session.id,
            "runtime": runtime,
        }
    }


async def run_turn(
    graph: Any,
    session: Session,
    user_input: HumanMessage,
    *,
    runtime: AgentRuntime,
) -> AsyncIterator[SseEvent]:
    phase = compute_phase(session.draft).value
    state: AgentState = initial_agent_state(
        session_id=session.id,
        draft=session.draft,
        phase=phase,
    )
    state["messages"] = [user_input]
    state["cards_shown"] = list(session.cards_shown)

    config = _graph_config(session, runtime)
    message_id = f"m_{uuid.uuid4().hex[:10]}"
    pending_custom: list[SseEvent] = []
    tokens: list[SseEvent] = []
    timer = TurnTimer()
    streamed_token_chars = 0
    final_messages: list[BaseMessage] = []

    try:
        async for mode, chunk in graph.astream(
            state,
            config=config,
            stream_mode=["messages", "custom"],
        ):
            if mode == "custom":
                payload = chunk
                if isinstance(payload, dict):
                    event_type = payload.get("type")
                    data = payload.get("data")
                    if event_type in ("ui_card", "draft") and isinstance(data, dict):
                        pending_custom.append(
                            SseEvent(event=event_type, data=data),
                        )
            elif mode == "messages":
                message_chunk, _meta = chunk
                if isinstance(message_chunk, AIMessageChunk) and message_chunk.content:
                    text = message_chunk.content
                    if isinstance(text, str) and text:
                        streamed_token_chars += len(text)
                        tokens.append(
                            SseEvent(
                                event="token",
                                data={"message_id": message_id, "text": text},
                            )
                        )
                elif isinstance(message_chunk, AIMessage) and message_chunk.content:
                    text = message_chunk.content
                    if isinstance(text, str) and text:
                        streamed_token_chars += len(text)
                        tokens.append(
                            SseEvent(
                                event="token",
                                data={"message_id": message_id, "text": text},
                            )
                        )

        snapshot = await graph.aget_state(config)
        final = cast(AgentState, snapshot.values)
        final_messages = list(final.get("messages", []))
        session.draft = final["draft"]
        session.cards_shown = set(final.get("cards_shown", []))

        if not tokens:
            for message in reversed(final["messages"]):
                if isinstance(message, AIMessage):
                    content = message.content
                    if isinstance(content, str) and content:
                        tokens.append(
                            SseEvent(
                                event="token",
                                data={"message_id": message_id, "text": content},
                            )
                        )
                        break

        for event in tokens:
            yield event
        for event in pending_custom:
            yield event

        done_phase = str(final.get("phase", phase))
        log_chat_turn(
            session_id=session.id,
            phase=done_phase,
            messages=final_messages,
            latency_ms=timer.elapsed_ms(),
            streamed_token_chars=streamed_token_chars,
            outcome="done",
        )
        yield SseEvent(event="done", data={"phase": done_phase})

    except Exception:
        logger.exception("agent turn failed")
        log_chat_turn(
            session_id=session.id,
            phase=phase,
            messages=final_messages,
            latency_ms=timer.elapsed_ms(),
            streamed_token_chars=streamed_token_chars,
            outcome="error",
        )
        yield SseEvent(
            event="error",
            data={
                "code": "agent_error",
                "message": "Sorry, something went wrong on our side. Please try again.",
            },
        )
