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

from app.agent.case_tools import CASE_TOOLS
from app.agent.channels import restamp_staff
from app.agent.e2e_scripts import scripted_model_for_session
from app.agent.form_mode import (
    FORM_MODE_NOTICE,
    build_form_mode_card,
    form_mode_cards,
)
from app.agent.model import ModelUnavailable, ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState, initial_agent_state
from app.agent.tools import ASSISTED_TOOLS, TOOLS
from app.api.cards import remember_confirm_card_keys
from app.api.schemas import UiCard
from app.config import Settings
from app.domain.rules import compute_phase
from app.domain.summary import build_draft_summary
from app.domain.tenant_prefill import apply_tenant_brand_pick_from_message
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
    tools = CASE_TOOLS if session.mode == "case" else ASSISTED_TOOLS if session.assisted else TOOLS
    if settings and settings.agent_mode == "scripted" and session.test_scenario:
        model = scripted_model_for_session(
            scenario=session.test_scenario,
            step_index=session.script_step,
        )
        configurable["bound_chat_model"] = model.bind_tools(tools)
    return {"configurable": configurable}


HISTORY_LIMIT = 20

FORM_MODE_RESUME_NOTE = (
    "[ui_event] form_mode_resume: the assistant was unavailable for a while and the user "
    "carried on in the cards. The current state is in the system message; don't ask again "
    "for anything already there."
)
FORM_MODE_STILL_DOWN = (
    "Our assistant still isn't available. You can keep going with the cards below, "
    "or ask us to call you."
)


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
    user_text = _text_of(user_input)
    if session.channel == "existing_tenant" and session.tenant_id:
        tenant = runtime.services.tenants.get_by_id(session.tenant_id)
        if tenant is not None:
            updated, written = apply_tenant_brand_pick_from_message(
                session.draft,
                tenant,
                runtime.master,
                user_text,
            )
            if written:
                session.draft = updated
                runtime.services.audit.record(
                    session.id,
                    "tenant_prefill",
                    actor="system",
                    payload={
                        "tenant_id": tenant.id,
                        "keys": written,
                        "source": "brand_message",
                    },
                )

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
    state["inquiry_seq"] = session.inquiry_seq
    if session.mode == "case":
        state["case_id"] = session.case_id
        state["contacts_draft"] = list(session.contacts_draft)
    state["channel"] = session.channel
    state["assisted"] = session.assisted
    state["tenant_id"] = session.tenant_id
    state["existing_cr_choice"] = session.existing_cr_choice
    turn_start_draft = session.draft.model_copy(deep=True)

    config = _graph_config(session, runtime, settings=settings)
    before = await graph.aget_state(config)
    prior_count = len((before.values or {}).get("messages", []))
    turn_input: list[BaseMessage] = [user_input]
    was_form_mode = session.form_mode
    if was_form_mode:
        # Trying the model again after form mode: it didn't see what happened in the cards.
        turn_input = [HumanMessage(content=FORM_MODE_RESUME_NOTE), user_input]
    if prior_count == 0 and session.has_user_messages():
        # The checkpointer is in memory; after a restart the transcript restores memory.
        history = _history_messages(session)
        state["messages"] = [*history, *turn_input]
    else:
        state["messages"] = turn_input

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
        if session.assisted:
            # Everything the executive typed this turn is `staff`, whichever path wrote it.
            session.draft, restamped = restamp_staff(turn_start_draft, session.draft)
            if restamped:
                summary = build_draft_summary(session.draft, runtime.master, restamped)
                yield SseEvent(event="draft", data=summary.model_dump())
        session.cards_shown = set(final.get("cards_shown", []))
        session.confirm_card_keys = dict(final.get("confirm_card_keys", session.confirm_card_keys))
        session.confirm_card_turns = dict(
            final.get("confirm_card_turns", session.confirm_card_turns),
        )
        session.inquiry_seq = int(final.get("inquiry_seq", session.inquiry_seq))
        if session.mode == "case" and "contacts_draft" in final:
            session.contacts_draft = list(final["contacts_draft"])
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

        if was_form_mode:
            # The model answered: back to chat; the card says so. Nothing is lost.
            session.form_mode = False
            runtime.services.audit.record(session.id, "form_mode_left", actor="system")
            back = build_form_mode_card(session.draft, active=False)
            yield SseEvent(event="ui_card", data=back.model_dump())

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

    except ModelUnavailable as unavailable:
        # Two model failures in this turn (L3 §3.14): keep what tools already saved, then
        # let the user finish from the cards.
        snapshot = await graph.aget_state(config)
        saved = cast(AgentState, snapshot.values or {})
        if "draft" in saved:
            session.draft = saved["draft"]
            session.cards_shown = set(saved.get("cards_shown", session.cards_shown))
            session.confirm_card_keys = dict(
                saved.get("confirm_card_keys", session.confirm_card_keys)
            )
            session.inquiry_seq = int(saved.get("inquiry_seq", session.inquiry_seq))
        entering = not session.form_mode
        session.form_mode = True
        if entering:
            runtime.services.audit.record(
                session.id, "form_mode_entered", actor="system", payload={"kind": unavailable.kind}
            )
        log_chat_turn(
            session_id=session.id,
            phase=phase,
            messages=final_messages,
            latency_ms=timer.elapsed_ms(),
            streamed_token_chars=streamed_token_chars,
            retractions=retractions,
            outcome="form_mode",
        )
        notice_id = _new_message_id()
        yield SseEvent(
            event="token",
            data={
                "message_id": notice_id,
                "text": FORM_MODE_NOTICE if entering else FORM_MODE_STILL_DOWN,
            },
        )
        for card_event in pending_cards:
            card_event["data"]["message_id"] = notice_id
            remember_confirm_card_keys(session, UiCard.model_validate(card_event["data"]))
            yield card_event
        for card in await form_mode_cards(session, runtime):
            card.message_id = notice_id
            remember_confirm_card_keys(session, card)
            yield SseEvent(event="ui_card", data=card.model_dump())
        summary = build_draft_summary(session.draft, runtime.master, [])
        yield SseEvent(event="draft", data=summary.model_dump())
        yield SseEvent(event="done", data={"phase": compute_phase(session.draft).value})

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
