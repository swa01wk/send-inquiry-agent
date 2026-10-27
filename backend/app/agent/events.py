"""Stream a single agent turn as SSE-shaped events.

Assistant text is forwarded as it is generated (token by token), so the user sees
the reply being written instead of waiting for the whole turn. Each LLM call that
produces text gets its own ``message_id`` (its own chat bubble). Draft updates are
forwarded immediately so the draft panel fills live; cards are held until the end
of the turn and attached to the final reply. When the guard rejects a reply it
emits ``retract_reply`` and we tell the frontend to remove that bubble.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict, cast

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from app.agent.e2e_scripts import scripted_model_for_session
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState, initial_agent_state
from app.agent.tools import TOOLS
from app.api.cards import remember_confirm_card_keys
from app.api.schemas import UiCard
from app.config import Settings
from app.domain.rules import compute_phase
from app.observability.turn_log import TurnTimer, log_chat_turn
from app.sessions import Session

logger = logging.getLogger(__name__)

EventType = Literal["token", "ui_card", "draft", "message_remove", "done", "error"]

_AGENT_NODE = "agent"


class SseEvent(TypedDict):
    event: EventType
    data: dict[str, Any]


def _graph_config(
    session: Session,
    runtime: AgentRuntime,
    *,
    settings: Settings | None = None,
) -> RunnableConfig:
    configurable: dict[str, object] = {
        "thread_id": session.id,
        "runtime": runtime,
    }
    if settings and settings.agent_mode == "scripted" and session.test_scenario:
        model = scripted_model_for_session(
            scenario=session.test_scenario,
            step_index=session.script_step,
        )
        configurable["bound_chat_model"] = model.bind_tools(TOOLS)
    return {"configurable": configurable}


HISTORY_LIMIT = 20


def _history_messages(session: Session) -> list[BaseMessage]:
    """The last messages the user saw, as model messages (used after a restart)."""
    restored: list[BaseMessage] = []
    for entry in session.transcript[-HISTORY_LIMIT:]:
        text = entry.get("text", "")
        if not text:
            continue
        if entry.get("role") == "user":
            restored.append(HumanMessage(content=text))
        else:
            restored.append(AIMessage(content=text))
    return restored


def _audit_turn(
    runtime: AgentRuntime,
    session_id: str,
    turn_messages: list[BaseMessage],
    retractions: int,
) -> None:
    """Agent tool calls and guard retractions for this turn (audit log v0)."""
    audit = runtime.services.audit
    for message in turn_messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                audit.record(
                    session_id,
                    "tool_called",
                    actor="agent",
                    payload={"layer": "agent", "name": call.get("name", "")},
                )
    if retractions:
        audit.record(
            session_id,
            "guard_verdict",
            actor="system",
            payload={"rule": "retract_reply", "retractions": retractions},
        )


def _new_message_id() -> str:
    return f"m_{uuid.uuid4().hex[:10]}"


def _text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return ""


class _ReplyTracker:
    """Maps each agent LLM call to a chat bubble id."""

    def __init__(self) -> None:
        self._ids: dict[str, str] = {}
        self._chunked: set[str] = set()
        self.latest_key: str | None = None
        self.last_text_id: str | None = None

    def key_for(self, meta: dict[str, Any]) -> str:
        return f"{meta.get('checkpoint_ns', '')}|{meta.get('langgraph_step', '')}"

    def note_call(self, key: str) -> None:
        self.latest_key = key

    def id_for(self, key: str) -> str:
        if key not in self._ids:
            self._ids[key] = _new_message_id()
        self.last_text_id = self._ids[key]
        return self._ids[key]

    def mark_chunked(self, key: str) -> None:
        self._chunked.add(key)

    def was_chunked(self, key: str) -> bool:
        return key in self._chunked

    def retract_latest(self) -> str | None:
        """Forget the latest call's bubble; return its id if it showed any text."""
        if self.latest_key is None or self.latest_key not in self._ids:
            return None
        removed = self._ids.pop(self.latest_key)
        self._chunked.discard(self.latest_key)
        if self.last_text_id == removed:
            remaining = list(self._ids.values())
            self.last_text_id = remaining[-1] if remaining else None
        return removed


async def run_turn(
    graph: Any,
    session: Session,
    user_input: HumanMessage,
    *,
    runtime: AgentRuntime,
    settings: Settings | None = None,
) -> AsyncIterator[SseEvent]:
    phase = compute_phase(session.draft).value
    session.turn_index += 1
    state: AgentState = initial_agent_state(
        session_id=session.id,
        draft=session.draft,
        phase=phase,
        turn_index=session.turn_index,
        confirm_card_turns=dict(session.confirm_card_turns),
    )
    state["cards_shown"] = list(session.cards_shown)
    state["confirm_card_keys"] = dict(session.confirm_card_keys)

    config = _graph_config(session, runtime, settings=settings)
    before = await graph.aget_state(config)
    prior_count = len((before.values or {}).get("messages", []))
    if prior_count == 0 and session.has_user_messages():
        # The checkpointer is in memory; after a restart the transcript restores memory.
        history = _history_messages(session)
        state["messages"] = [*history, user_input]
    else:
        state["messages"] = [user_input]

    bound = (config.get("configurable") or {}).get("bound_chat_model")
    replies = _ReplyTracker()
    pending_cards: list[SseEvent] = []
    timer = TurnTimer()
    streamed_token_chars = 0
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
                if event_type == "draft" and isinstance(data, dict):
                    yield SseEvent(event="draft", data=data)
                elif event_type == "ui_card" and isinstance(data, dict):
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
                # Full message for a call we already streamed chunk by chunk.
                continue
            text = _text_of(message_chunk)
            if not text:
                continue
            if is_chunk:
                replies.mark_chunked(key)
            streamed_token_chars += len(text)
            yield SseEvent(
                event="token",
                data={"message_id": replies.id_for(key), "text": text},
            )

        snapshot = await graph.aget_state(config)
        final = cast(AgentState, snapshot.values)
        final_messages = list(final.get("messages", []))
        _audit_turn(runtime, session.id, final_messages[prior_count:], retractions)
        session.draft = final["draft"]
        session.cards_shown = set(final.get("cards_shown", []))
        session.confirm_card_keys = dict(final.get("confirm_card_keys", session.confirm_card_keys))
        session.confirm_card_turns = dict(
            final.get("confirm_card_turns", session.confirm_card_turns),
        )
        if isinstance(bound, ScriptedChatModel):
            session.script_step = bound._step_index

        if replies.last_text_id is None:
            # Nothing was streamed (e.g. a model without streaming); send the final reply.
            for message in reversed(final_messages):
                if isinstance(message, AIMessage) and _text_of(message):
                    reply_id = _new_message_id()
                    replies.last_text_id = reply_id
                    yield SseEvent(
                        event="token",
                        data={"message_id": reply_id, "text": _text_of(message)},
                    )
                    break

        for card_event in pending_cards:
            if card_event["data"].get("message_id") is None and replies.last_text_id:
                card_event["data"]["message_id"] = replies.last_text_id
            card = UiCard.model_validate(card_event["data"])
            remember_confirm_card_keys(session, card)
            yield card_event

        done_phase = str(final.get("phase", phase))
        log_chat_turn(
            session_id=session.id,
            phase=done_phase,
            messages=final_messages,
            latency_ms=timer.elapsed_ms(),
            streamed_token_chars=streamed_token_chars,
            retractions=retractions,
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
            retractions=retractions,
            outcome="error",
        )
        yield SseEvent(
            event="error",
            data={
                "code": "agent_error",
                "message": "Sorry, something went wrong on our side. Please try again.",
            },
        )
