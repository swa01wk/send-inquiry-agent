"""Deterministic post-agent guard (spec section 5).

Runs after the agent's final reply each turn. It never talks to the user itself;
when a reply breaks a rule it retracts that reply (the frontend removes the bubble)
and sends the agent back once with a short instruction.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.config import get_stream_writer

from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.cards import build_document_upload_card, build_review_card
from app.api.schemas import UiCard
from app.domain.rules import compute_phase
from app.domain.summary import build_draft_summary

GUARD_PREFIX = "[ui_event] guard:"

# A claim that the inquiry was submitted, e.g. "your inquiry has been submitted",
# "I've sent your inquiry", "your reference number is GEO-…". Plain uses of the word
# "reference" ("for your reference") do not match.
_FALSE_SUBMIT_RE = re.compile(
    r"\b(inquiry|enquiry|application|request)\b[^.!?\n]{0,40}?\b(has been|have been|was|is now|is)\s+"
    r"(submitted|sent|received)\b"
    r"|\bI(?:'ve| have)\s+(submitted|sent)\s+(your|the)\b"
    r"|\byour reference(?: number)? is\b",
    re.IGNORECASE,
)
_SIGN_IN_RE = re.compile(r"sign\s*in", re.IGNORECASE)

# Signals that a user message carries inquiry data the agent should have saved.
# 10 digits, but not a local mobile number (05XXXXXXXX).
_CR_NUMBER_RE = re.compile(r"\b(?!05)\d{10}\b")
_DATA_HINT_RE = re.compile(
    r"(@[\w-]+\.|\+?966|\b05\d{8}\b|\b\d{10}\b|\b(LLC|Ltd|Trading|Co\.)\b|"
    r"\bmall\s+[a-z]\b|\b(kiosk|boutique|restaurant|caf[eé]|coffee|store|shop)\b|"
    r"\b\d+\s*(sqm|sq\.?\s*m|square)\b|\b\d+\s*(k|,000)\b)",
    re.IGNORECASE,
)
_QUESTION_START_RE = re.compile(
    r"^\s*(what|which|how|where|when|why|who|can|could|do|does|is|are|should|will)\b",
    re.IGNORECASE,
)
_CAPTURE_TOOLS = {"update_draft", "verify_cr"}


def _content_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(part) for part in content)
    return ""


def _last_ai_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage):
            return _content_text(message)
    return ""


def _current_turn(state: AgentState) -> tuple[str, list[BaseMessage]]:
    """The user's input for this turn and the messages that followed it."""
    messages = state["messages"]
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, HumanMessage) and not _content_text(message).startswith(
            GUARD_PREFIX
        ):
            return _content_text(message), list(messages[index + 1 :])
    return "", []


def _tools_called(messages: list[BaseMessage]) -> set[str]:
    names: set[str] = set()
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                names.add(str(call.get("name", "")))
    return names


def message_likely_has_inquiry_data(text: str) -> bool:
    """True when a user message looks like it carries details to save (not a question)."""
    stripped = text.strip()
    if not stripped or stripped.startswith("[ui_event]"):
        return False
    if stripped.endswith("?") or _QUESTION_START_RE.match(stripped):
        return False
    return _DATA_HINT_RE.search(stripped) is not None


def _missed_capture_note(state: AgentState, phase: str) -> str | None:
    user_text, turn_messages = _current_turn(state)
    if not user_text or user_text.startswith("[ui_event]"):
        return None
    called = _tools_called(turn_messages)
    if phase == "gate" and _CR_NUMBER_RE.search(user_text) and "verify_cr" not in called:
        return (
            f"{GUARD_PREFIX} The user's last message contains a CR number. "
            "Call verify_cr with it before replying."
        )
    if (
        phase in ("gate", "collecting", "verifying")
        and not (called & _CAPTURE_TOOLS)
        and message_likely_has_inquiry_data(user_text)
    ):
        return (
            f"{GUARD_PREFIX} The user's last message looks like it contains inquiry details "
            "you did not save. If it does, call update_draft with every field you can find "
            "in it, then reply. If it doesn't, simply reply again."
        )
    return None


def _emit_draft(state: AgentState, runtime: AgentRuntime, changed_keys: list[str]) -> None:
    writer = get_stream_writer()
    if writer is None:
        return
    summary = build_draft_summary(state["draft"], runtime.master, changed_keys)
    writer({"type": "draft", "data": summary.model_dump()})


def _emit_card(card: UiCard, writer: Any) -> None:
    if writer is None:
        return
    writer({"type": "ui_card", "data": card.model_dump()})


def guard_node(state: AgentState, *, runtime: AgentRuntime) -> dict[str, Any]:
    draft = state["draft"]
    phase = compute_phase(draft).value
    cards_shown = list(state["cards_shown"])
    guard_retries = state["guard_retries"]
    note: str | None = None

    writer = get_stream_writer()

    ai_text = _last_ai_text(state)
    _user_text, turn_messages = _current_turn(state)
    status_lookup = "get_inquiry_status" in _tools_called(turn_messages)
    if guard_retries < 1:
        if (
            draft.reference is None
            and not status_lookup
            and ai_text
            and _FALSE_SUBMIT_RE.search(ai_text)
        ):
            note = (
                f"{GUARD_PREFIX} Do not tell the user the inquiry was submitted. "
                "It is only submitted when a submitted reference ui_event arrives. "
                "Reply again without that claim."
            )
        elif phase == "existing_account" and ai_text and not _SIGN_IN_RE.search(ai_text):
            note = (
                f"{GUARD_PREFIX} This user already has an account. "
                "Reply again, kindly pointing them to Sign In on Tenant Central."
            )
        else:
            note = _missed_capture_note(state, phase)

    if note is not None:
        # Take the rejected reply off the user's screen; the agent replies again.
        if writer is not None:
            writer({"type": "retract_reply", "data": {}})
        return {
            "phase": phase,
            "cards_shown": cards_shown,
            "guard_retries": guard_retries + 1,
            "retry_agent": True,
            "messages": [HumanMessage(content=note)],
        }

    _emit_draft(state, runtime, [])

    if phase == "documents" and "documents" not in cards_shown:
        card = build_document_upload_card(
            draft,
            runtime.master,
            max_mb=runtime.settings.max_upload_mb,
        )
        _emit_card(card, writer)
        cards_shown.append("documents")

    if phase == "review" and "review" not in cards_shown:
        card = build_review_card(draft, runtime.master)
        _emit_card(card, writer)
        cards_shown.append("review")

    return {
        "phase": phase,
        "cards_shown": cards_shown,
        "guard_retries": guard_retries,
        "retry_agent": False,
    }


def after_guard(state: AgentState) -> str:
    if state.get("retry_agent"):
        return "agent"
    return "__end__"
