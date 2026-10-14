"""Deterministic post-agent guard (spec section 5)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer

from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.cards import build_document_upload_card, build_review_card
from app.api.schemas import UiCard
from app.domain.rules import compute_phase
from app.domain.summary import build_draft_summary

_FALSE_SUBMIT_RE = re.compile(
    r"submitted|sent your inquiry|reference",
    re.IGNORECASE,
)
_SIGN_IN_RE = re.compile(r"sign\s*in", re.IGNORECASE)


def _last_ai_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(str(part) for part in content)
    return ""


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
    messages: list[HumanMessage] = []
    retry_agent = False

    writer = get_stream_writer()
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

    ai_text = _last_ai_text(state)
    if draft.reference is None and ai_text and _FALSE_SUBMIT_RE.search(ai_text):
        if guard_retries < 1:
            retry_agent = True
            guard_retries += 1
            messages.append(
                HumanMessage(
                    content=(
                        "[ui_event] guard: Do not tell the user the inquiry was submitted "
                        "until a submitted reference ui_event arrives."
                    )
                )
            )

    if phase == "existing_account" and ai_text and not _SIGN_IN_RE.search(ai_text):
        if guard_retries < 1 and not retry_agent:
            retry_agent = True
            guard_retries += 1
            messages.append(
                HumanMessage(
                    content=(
                        "[ui_event] guard: This user already has an account. "
                        "Point them to Sign In on Tenant Central."
                    )
                )
            )

    update: dict[str, Any] = {
        "phase": phase,
        "cards_shown": cards_shown,
        "guard_retries": guard_retries,
        "retry_agent": retry_agent,
    }
    if messages:
        update["messages"] = messages
    return update


def after_guard(state: AgentState) -> str:
    if state.get("retry_agent"):
        return "agent"
    return "__end__"
