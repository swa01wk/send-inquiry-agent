"""Post-agent guard for the reviewer assistant (L4 §3.6)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.guard import GUARD_PREFIX, after_guard
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.domain.rules import compute_phase

_DECISION_TAKEN_RE = re.compile(
    r"\b(?:I(?:'ve| have|'ll| will)|this (?:case|inquiry|application) (?:has|was))\s+"
    r"(?:been\s+)?(?:approved|rejected|denied)\b",
    re.IGNORECASE,
)
_REQUEST_SENT_RE = re.compile(
    r"\b(?:I(?:'ve| have|'ll| will)|the (?:case|request))\s+"
    r"(?:been\s+)?(?:requested|sent)\s+(?:a\s+)?(?:re-?upload|contacts|sales\s+data)\b",
    re.IGNORECASE,
)


def _current_turn(state: AgentState) -> tuple[str, list[BaseMessage]]:
    messages = state["messages"]
    turn_start = 0
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            turn_start = index
    turn = messages[turn_start:]
    user_text = ""
    for message in turn:
        if isinstance(message, HumanMessage):
            raw = message.content
            user_text = raw if isinstance(raw, str) else str(raw)
    return user_text, turn


def _false_decision_note(ai_text: str) -> str | None:
    if _DECISION_TAKEN_RE.search(ai_text) or _REQUEST_SENT_RE.search(ai_text):
        return (
            f"{GUARD_PREFIX} Do not say you approved, rejected or sent a request. "
            "The reviewer decides using the actions panel; you only prepare suggestions."
        )
    return None


def reviewer_guard_node(state: AgentState, *, runtime: AgentRuntime) -> dict[str, Any]:
    del runtime
    guard_retries = int(state.get("guard_retries", 0))
    if guard_retries >= 1:
        return {"guard_retries": guard_retries, "retry_agent": False}

    user_text, turn = _current_turn(state)
    ai_text = ""
    for message in reversed(turn):
        if isinstance(message, AIMessage):
            content = message.content
            ai_text = content if isinstance(content, str) else str(content)
            break

    note = _false_decision_note(ai_text) if ai_text else None
    if note is not None and not user_text.startswith("[ui_event] guard:"):
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        if writer is not None:
            writer({"type": "retract_reply", "data": {}})
        return {
            "phase": compute_phase(state["draft"]).value,
            "guard_retries": guard_retries + 1,
            "retry_agent": True,
            "messages": [HumanMessage(content=note)],
        }

    return {
        "phase": compute_phase(state["draft"]).value,
        "guard_retries": guard_retries,
        "retry_agent": False,
    }


__all__ = ["reviewer_guard_node", "after_guard"]
