"""When to require a tool call on the agent turn."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.state import AgentState
from app.domain.models import Phase
from app.domain.rules import compute_phase

_CR_NUMBER = re.compile(r"\b\d{10}\b")
_DATA_HINT = re.compile(
    r"(@|\+966|\b\d{10}\b|LLC|Ltd|Trading|Road|Mall|Street|example\.com|"
    r"[\u0600-\u06FF]|riyadh|jeddah|dammam|\b(store|specialty|kiosk)\b)",
    re.IGNORECASE,
)


def message_likely_has_inquiry_data(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("[ui_event]"):
        return False
    lower = stripped.lower()
    if "skip" in lower and "cr" in lower:
        return True
    return _DATA_HINT.search(stripped) is not None


def preferred_tool_name(state: AgentState) -> str | None:
    messages = state["messages"]
    if not messages:
        return None
    last = messages[-1]
    if not isinstance(last, HumanMessage):
        return None
    content = last.content
    if not isinstance(content, str):
        return None
    if content.strip().startswith("[ui_event]"):
        return None

    lower = content.lower()
    phase = compute_phase(state["draft"])

    if phase == Phase.GATE:
        if _CR_NUMBER.search(content):
            return "verify_cr"
        if "skip" in lower and "cr" in lower:
            return "skip_cr"
        return None

    if phase == Phase.COLLECTING and message_likely_has_inquiry_data(content):
        return "update_draft"

    return None


def invoke_tool_choice(state: AgentState) -> dict[str, Any]:
    name = preferred_tool_name(state)
    if name is None:
        return {}
    return {"tool_choice": {"type": "function", "function": {"name": name}}}
