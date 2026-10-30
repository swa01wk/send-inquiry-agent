"""Post-agent guard for the case assistant (L4 §3.5)."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.agent.guard import GUARD_PREFIX, after_guard
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.domain.rules import compute_phase
from app.policy.config import get_policy
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


def _contacts_card_missing_note(
    turn: list[BaseMessage], case: Case | None, contacts_draft: list[dict[str, Any]]
) -> str | None:
    """Contacts saved this turn for an open request, every required role there, but no card.

    The applicant sends contacts from the review card, so a turn that captures them must show
    it (case prompt, "Contacts"). Live eval "Case: contacts bundle" missed it about 1 run in 3.
    """
    if case is None or case.open_request("contacts") is None:
        return None
    called: set[str] = set()
    update_ids: set[str] = set()
    for message in turn:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                called.add(call["name"])
                if call["name"] == "update_contacts" and call.get("id"):
                    update_ids.add(str(call["id"]))
    if "update_contacts" not in called or "show_contacts_review" in called:
        return None
    results = [m for m in turn if isinstance(m, ToolMessage) and m.tool_call_id in update_ids]
    last = results[-1].content if results else ""
    if not (isinstance(last, str) and last.startswith("Contacts draft updated")):
        return None
    roles = {c.get("role") for c in contacts_draft}
    if not set(get_policy().second_level_contacts.required) <= roles:
        return None
    return (
        f"{GUARD_PREFIX} The contacts are saved but the applicant can't see them yet. Call "
        "`show_contacts_review` now, then say in one line what you captured and point them to "
        "**Send contacts** on the card."
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
    if note is None:
        note = _contacts_card_missing_note(turn, case, list(state.get("contacts_draft") or []))
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
