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

from app.agent.confirm_policy import keys_blocked_from_confirmation
from app.agent.mall_match import unmatched_mall_phrases
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.cards import build_document_upload_card, build_review_card
from app.api.schemas import UiCard
from app.domain.models import FieldKey, FieldValue, InquiryDraft
from app.domain.rules import compute_phase
from app.domain.summary import build_draft_summary

GUARD_PREFIX = "[ui_event] guard:"

# A claim that the inquiry was submitted, e.g. "your inquiry has been submitted",
# "I've sent your inquiry", "your reference number is GEO-…". Plain uses of the word
# "reference" ("for your reference") do not match.
_FALSE_SUBMIT_RE = re.compile(
    r"\b(inquiry|enquiry|application|request)\b[^.!?\n]{0,40}?"
    r"\b(has been|have been|was|is now|is)\s+"
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
    r"[\u0600-\u06FF]{3,}|"
    r"\bmall\s+[a-z]\b|\b(kiosk|boutique|restaurant|caf[eé]|coffee|store|shop)\b|"
    r"\b\d+\s*(sqm|sq\.?\s*m|square)\b|\b\d+\s*(k|,000)\b)",
    re.IGNORECASE,
)
_QUESTION_START_RE = re.compile(
    r"^\s*(what|which|how|where|when|why|who|can|could|do|does|is|are|should|will)\b",
    re.IGNORECASE,
)
_CAPTURE_TOOLS = {"update_draft", "verify_cr"}
_REASK_BRAND_RE = re.compile(r"\bbrand name\b", re.IGNORECASE)
_BULK_INQUIRY_RE = re.compile(
    r"@.*?(?:\+?966|\b05\d{8}\b)|(?:\+?966|\b05\d{8}\b).*?@",
    re.IGNORECASE | re.DOTALL,
)


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


def _field_has_value(draft: Any, key: FieldKey) -> bool:
    value = draft.fields[key].value
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, list) and not value:
        return False
    return True


def _is_bulk_inquiry_message(text: str) -> bool:
    if "@" not in text or not _BULK_INQUIRY_RE.search(text):
        return False
    return bool(
        re.search(
            r"\b(LLC|Ltd|Trading|caf[eé]|kiosk|restaurant|mall|street)\b",
            text,
            re.IGNORECASE,
        )
    )


def _incomplete_bulk_capture_note(state: AgentState, phase: str) -> str | None:
    user_text, turn_messages = _current_turn(state)
    if phase not in ("gate", "collecting", "verifying") or not _is_bulk_inquiry_message(user_text):
        return None
    if "update_draft" not in _tools_called(turn_messages):
        return None
    draft = state["draft"]
    missing: list[str] = []
    for key in (FieldKey.BRAND_NAME_EN, FieldKey.UNIT_TYPE, FieldKey.EMAIL):
        if not _field_has_value(draft, key):
            missing.append(key.value)
    if not (_field_has_value(draft, FieldKey.MOBILE) or _field_has_value(draft, FieldKey.LANDLINE)):
        missing.append("contact_number")
    if not missing:
        return None
    return (
        f"{GUARD_PREFIX} The user's message combined company, brand, and contact details, "
        f"but these draft fields are still empty: {', '.join(missing)}. "
        "Call update_draft with every field you can extract from their message before replying."
    )


def _brand_reask_note(state: AgentState, ai_text: str) -> str | None:
    if not _REASK_BRAND_RE.search(ai_text):
        return None
    if not _field_has_value(state["draft"], FieldKey.BRAND_NAME_EN):
        return None
    return (
        f"{GUARD_PREFIX} The user already provided a brand name. "
        "Do not ask for 'brand name' again in your reply."
    )


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


def _clear_malls_for_unknown_name(
    draft: InquiryDraft,
    user_text: str,
    master: Any,
    turn_messages: list[BaseMessage],
) -> tuple[InquiryDraft, str | None, bool]:
    """Drop mall ids when the user named a mall that is not in seed data."""
    unmatched = unmatched_mall_phrases(user_text, master)
    if not unmatched or not _field_has_value(draft, FieldKey.MALLS):
        return draft, None, False
    if "show_mall_picker" in _tools_called(turn_messages):
        return draft, None, False
    cleared = draft.model_copy(deep=True)
    cleared.fields[FieldKey.MALLS] = FieldValue(value=[], source=None, confirmed=False)
    label = unmatched[0]
    note = (
        f"{GUARD_PREFIX} The user named «{label}», which is not in seeded mall data. "
        "Do not write a different mall id. Leave malls empty or call show_mall_picker "
        "for the city they mean, then reply."
    )
    return cleared, note, True


def _unconfirm_doubted_fields(state: AgentState) -> tuple[Any, list[str]]:
    user_text, _ = _current_turn(state)
    blocked = keys_blocked_from_confirmation(user_text)
    if not blocked:
        return state["draft"], []
    draft = state["draft"].model_copy(deep=True)
    changed: list[str] = []
    for key_str in blocked:
        try:
            key = FieldKey(key_str)
        except ValueError:
            continue
        field = draft.fields[key]
        if field.confirmed:
            draft.fields[key] = field.model_copy(update={"confirmed": False})
            changed.append(key_str)
    return draft, changed


def guard_node(state: AgentState, *, runtime: AgentRuntime) -> dict[str, Any]:
    draft, doubt_unconfirmed = _unconfirm_doubted_fields(state)
    user_text, turn_messages = _current_turn({**state, "draft": draft})
    draft, unknown_mall_note, malls_cleared = _clear_malls_for_unknown_name(
        draft,
        user_text,
        runtime.master,
        turn_messages,
    )
    draft_changed = list(doubt_unconfirmed)
    if malls_cleared:
        draft_changed.append(FieldKey.MALLS.value)
    phase = compute_phase(draft).value
    cards_shown = list(state["cards_shown"])
    guard_retries = state["guard_retries"]
    note: str | None = None

    writer = get_stream_writer()

    ai_text = _last_ai_text(state)
    status_lookup = "get_inquiry_status" in _tools_called(turn_messages)
    if guard_retries >= 1:
        unknown_mall_note = None
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
            note = (
                unknown_mall_note
                or _brand_reask_note({**state, "draft": draft}, ai_text)
                or _incomplete_bulk_capture_note({**state, "draft": draft}, phase)
                or _missed_capture_note({**state, "draft": draft}, phase)
            )

    if note is not None:
        # Take the rejected reply off the user's screen; the agent replies again.
        if writer is not None:
            writer({"type": "retract_reply", "data": {}})
        return {
            "draft": draft,
            "phase": phase,
            "cards_shown": cards_shown,
            "guard_retries": guard_retries + 1,
            "retry_agent": True,
            "messages": [HumanMessage(content=note)],
        }

    _emit_draft({**state, "draft": draft}, runtime, draft_changed)

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
        "draft": draft,
        "phase": phase,
        "cards_shown": cards_shown,
        "guard_retries": guard_retries,
        "retry_agent": False,
    }


def after_guard(state: AgentState) -> str:
    if state.get("retry_agent"):
        return "agent"
    return "__end__"
