"""Post-agent guard for the case assistant (L4 §3.5)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.guard import GUARD_PREFIX, after_guard
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.domain.rules import compute_phase
from app.workflow.models import Case, CaseStatus

_DOC_RESUBMITTED_RE = re.compile(
    r"\b(?:documents?|files?|brand\s+profile|company\s+profile)\s+"
    r"(?:have\s+been|has\s+been|were|was)\s+resubmitted\b",
    re.IGNORECASE,
)
_CONTACTS_SENT_RE = re.compile(
    r"\b(?:contacts?|contact\s+details)\s+"
    r"(?:have\s+been|has\s+been|were|was)\s+(?:sent|submitted)\b",
    re.IGNORECASE,
)
_SALES_SENT_RE = re.compile(
    r"\bsales\s+data\s+(?:has\s+been|was)\s+(?:sent|submitted)\b",
    re.IGNORECASE,
)
_SENT_TO_YARDI_RE = re.compile(
    r"\bsent\s+to\s+(?:yardi|the\s+leasing\s+team'?s?\s+system)\b",
    re.IGNORECASE,
)
_APPROVAL_CLAIM_RE = re.compile(
    r"\b(?:your\s+inquiry|inquiry|case|application)\s+"
    r"(?:has\s+been|was|is\s+now)\s+approved\b",
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


def _ui_events_in_turn(turn: list[BaseMessage]) -> str:
    parts: list[str] = []
    for message in turn:
        if not isinstance(message, HumanMessage):
            continue
        text = message.content if isinstance(message.content, str) else str(message.content)
        if text.startswith("[ui_event]"):
            parts.append(text)
    return "\n".join(parts)


def _approval_claim_allowed(case: Case | None) -> bool:
    if case is None:
        return False
    return case.status in (
        CaseStatus.SECOND_REVIEW,
        CaseStatus.APPROVED,
        CaseStatus.SENT_TO_YARDI,
    )


def _false_outcome_note(ai_text: str, turn: list[BaseMessage], case: Case | None) -> str | None:
    notes = _ui_events_in_turn(turn)
    flagged = False

    if _DOC_RESUBMITTED_RE.search(ai_text) and "documents_resubmitted" not in notes:
        flagged = True
    if _CONTACTS_SENT_RE.search(ai_text) and "contacts_submitted" not in notes:
        flagged = True
    if _SALES_SENT_RE.search(ai_text) and "sales_data_submitted" not in notes:
        flagged = True
    if _SENT_TO_YARDI_RE.search(ai_text) and not (case and case.status == CaseStatus.SENT_TO_YARDI):
        flagged = True
    if _APPROVAL_CLAIM_RE.search(ai_text) and not _approval_claim_allowed(case):
        flagged = True

    if not flagged:
        return None
    return (
        f"{GUARD_PREFIX} Do not say documents were resubmitted, contacts or sales data were "
        "sent, or the case was approved or sent to Yardi unless the matching `[ui_event]` "
        "note is in this turn (documents_resubmitted, contacts_submitted, sales_data_submitted)."
    )


def case_guard_node(state: AgentState, *, runtime: AgentRuntime) -> dict[str, Any]:
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

    case_id = state.get("case_id")
    case = runtime.services.cases.get(case_id) if case_id else None
    note = _false_outcome_note(ai_text, turn, case) if ai_text else None
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


__all__ = ["case_guard_node", "after_guard"]
