"""Deterministic post-agent guard (spec section 5).

Deterministic parsers may write to the draft only on exact, unambiguous matches
(e.g. a full seeded mall name). Otherwise they produce a guard note for the agent,
or write ``source=derived`` (unconfirmed) so the agent shows the value before it
can be confirmed. Never write ``source=user`` from a heuristic.

Runs after the agent's final reply each turn. It never talks to the user itself;
when a reply breaks a rule it retracts that reply (the frontend removes the bubble)
and sends the agent back once with a short instruction.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.config import get_stream_writer

from app.agent.brand_infer import fill_brands_from_user_message, user_message_names_brand
from app.agent.confirm_policy import keys_blocked_from_confirmation
from app.agent.contact_infer import (
    contact_fields_ready,
    message_has_contact_line,
    parse_contact_from_message,
)
from app.agent.mall_match import fill_mentioned_malls, unknown_mall_phrases
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.cards import (
    VERIFICATION_CARD_ID,
    build_document_upload_card,
    build_review_card,
)
from app.api.channel_cards import basic_info_missing, build_send_link_card
from app.api.schemas import UiCard
from app.domain.models import NEEDS_CONFIRMATION, FieldKey
from app.domain.rules import compute_phase, contact_verified
from app.domain.summary import build_draft_summary
from app.domain.validation import normalise_digits

GUARD_PREFIX = "[ui_event] guard:"

# A claim that the inquiry was submitted, e.g. "your inquiry has been submitted",
# "I've sent your inquiry", "your reference number is GEO-…". Plain uses of the word
# "reference" ("for your reference") do not match.
_FALSE_SUBMIT_RE = re.compile(
    r"\b(inquiry|enquiry|application|request)\b[^.!?\n]{0,40}?"
    r"\b(has been|have been|was|is now|is)\s+"
    r"(submitted|sent|received)\b"
    r"|\bI(?:'ve| have)\s+(?:submitted|sent)\s+(?:your|the)\s+"
    r"(?:inquiry|enquiry|application|request)\b"
    r"|\byour reference(?: number)? is\b",
    re.IGNORECASE,
)
# "once / after / when the inquiry is sent" describes what happens later, not a claim.
_CONDITIONAL_BEFORE_RE = re.compile(
    r"\b(once|after|when|whenever|until|before|as soon as|if)\s+(?:(?:the|your)\s+)?$",
    re.IGNORECASE,
)
_SIGN_IN_RE = re.compile(r"sign\s*in", re.IGNORECASE)


def claims_submission(text: str) -> bool:
    """True if the text says the inquiry was submitted, ignoring conditional mentions."""
    for match in _FALSE_SUBMIT_RE.finditer(text):
        before = text[max(0, match.start() - 24) : match.start()]
        if _CONDITIONAL_BEFORE_RE.search(before):
            continue
        return True
    return False


# Signals that a user message carries inquiry data the agent should have saved.
# 10 digits, but not a local mobile number (05XXXXXXXX).
_CR_NUMBER_RE = re.compile(r"\b(?!05)\d{10}\b")
_DATA_HINT_RE = re.compile(
    r"(@[\w-]+\.|\+?966|\+[1-9](?:[\s-]?\d){7,14}\b|\b05\d{8}\b|\b\d{10}\b|\b(LLC|Ltd|Trading|Co\.)\b|"
    r"\bmall\s+[a-z]\b|\b(kiosk|boutique|restaurant|caf[eé]|coffee|store|shop)\b|"
    r"\b\d+\s*(sqm|sq\.?\s*m|square)\b|\b\d+\s*(k|,000)\b|"
    r"كشك|متجر|مطعم|مقهى|مول)",
    re.IGNORECASE,
)
_QUESTION_START_RE = re.compile(
    r"^\s*(what|which|how|where|when|why|who|can|could|do|does|is|are|should|will)\b",
    re.IGNORECASE,
)
_CAPTURE_TOOLS = {"update_draft", "verify_cr"}
_ASK_WHAT_BRAND_RE = re.compile(
    r"\bwhat(?:'s|\s+is)\s+(?:your|the)\s+brand\b",
    re.IGNORECASE,
)
_TELL_BRAND_NAME_RE = re.compile(
    r"\btell me\s+(?:your|the)\s+brand name\b",
    re.IGNORECASE,
)
_BRAND_NAME_QUESTION_RE = re.compile(
    r"[^.!\n]*\bbrand name\b[^.!\n]*[?؟]",
    re.IGNORECASE,
)
_BULK_INQUIRY_RE = re.compile(
    r"@.*?(?:\+?966|\+[1-9](?:[\s-]?\d){7,14}\b|\b05\d{8}\b)"
    r"|(?:\+?966|\+[1-9](?:[\s-]?\d){7,14}\b|\b05\d{8}\b).*?@",
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
            # Digits normalised so every numeric check sees Arabic-Indic digits (L3 §3.10).
            return normalise_digits(_content_text(message)), list(messages[index + 1 :])
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
    stripped = normalise_digits(text).strip()
    if not stripped or stripped.startswith("[ui_event]"):
        return False
    if stripped.endswith(("?", "؟")) or _QUESTION_START_RE.match(stripped):
        return False
    return _DATA_HINT_RE.search(stripped) is not None


def reply_asks_for_brand_name(ai_text: str) -> bool:
    if _ASK_WHAT_BRAND_RE.search(ai_text):
        return True
    if _TELL_BRAND_NAME_RE.search(ai_text):
        return True
    return _BRAND_NAME_QUESTION_RE.search(ai_text) is not None


def _reply_asks_for_brand_name(ai_text: str) -> bool:
    return reply_asks_for_brand_name(ai_text)


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
            r"\b(LLC|Ltd|Trading|caf[eé]|kiosk|restaurant|mall|street)\b|"
            r"كشك|متجر|مطعم|مقهى|مول",
            text,
            re.IGNORECASE,
        )
    )


def _missing_send_verification_note(
    state: AgentState,
    draft: Any,
    user_text: str,
    turn_messages: list[BaseMessage],
    cards_shown: list[str],
) -> str | None:
    if VERIFICATION_CARD_ID in cards_shown or contact_verified(draft):
        return None
    if _is_bulk_inquiry_message(user_text):
        return None
    if not message_has_contact_line(user_text) or not contact_fields_ready(draft):
        return None
    if "send_verification" in _tools_called(turn_messages):
        return None
    return (
        f"{GUARD_PREFIX} The user sent name, email, and phone. "
        "Call send_verification before you reply."
    )


def _incomplete_contact_capture_note(
    state: AgentState,
    draft: Any,
    user_text: str,
    phase: str,
) -> str | None:
    if phase not in ("gate", "collecting", "verifying"):
        return None
    if _is_bulk_inquiry_message(user_text):
        return None
    if not message_has_contact_line(user_text) or contact_fields_ready(draft):
        return None
    parsed = parse_contact_from_message(user_text)
    example = ""
    if parsed:
        first, last, _email, _phone = parsed
        example = f" (e.g. {first!r} / {last!r})"
    return (
        f"{GUARD_PREFIX} The user gave contact details; save first_name, last_name, email "
        "and contact_number with update_draft (split the full name: first word = first name, "
        f"rest = last name){example}"
        + (
            ", then call show_application_link."
            if state.get("assisted")
            else ", then call send_verification."
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
    if not _reply_asks_for_brand_name(ai_text):
        return None
    draft = state["draft"]
    user_text, _ = _current_turn(state)
    if _field_has_value(draft, FieldKey.BRAND_NAME_EN) or _field_has_value(
        draft, FieldKey.BRAND_NAME_AR
    ):
        known = True
    else:
        known = user_message_names_brand(user_text)
    if not known:
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


def _unknown_mall_note(
    user_text: str,
    master: Any,
    turn_messages: list[BaseMessage],
) -> str | None:
    unknown = unknown_mall_phrases(user_text, master)
    if not unknown:
        return None
    if "show_mall_picker" in _tools_called(turn_messages):
        return None
    label = unknown[0]
    return (
        f"{GUARD_PREFIX} The user named «{label}», which is not in seeded mall data. "
        "Do not write a different mall id. Leave malls empty or call show_mall_picker "
        "for the city they mean, then reply."
    )


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
        # Only derived or prefilled values need the user's acceptance; what the user
        # typed themselves stays as it is.
        if field.confirmed and field.source in NEEDS_CONFIRMATION:
            draft.fields[key] = field.model_copy(update={"confirmed": False})
            changed.append(key_str)
    return draft, changed


_ASSISTED_AGENT_SENDS_VERIFICATION = re.compile(
    r"\b(?:I(?:'m|\s+am)\s+sending|I(?:'ve|\s+have)\s+sent|sending you)\b"
    r"[^.!?\n]{0,120}?"
    r"\b(?:verification link|sms code|one-time code|link to verify)\b",
    re.IGNORECASE,
)


def _assisted_application_link_note(
    state: AgentState,
    draft: Any,
    turn_messages: list[BaseMessage],
    cards_shown: list[str],
) -> str | None:
    if not state.get("assisted"):
        return None
    if basic_info_missing(draft):
        return None
    if "show_application_link" in _tools_called(turn_messages):
        return None
    if "send_link" in cards_shown:
        payload = build_send_link_card(draft).payload
        if payload.get("can_send"):
            return None
    return (
        f"{GUARD_PREFIX} Basic info is complete: call show_application_link now. "
        "Don't say you're sending a verification link or code."
    )


def _assisted_verification_claim_note(state: AgentState, ai_text: str) -> str | None:
    if not state.get("assisted") or not ai_text:
        return None
    if not _ASSISTED_AGENT_SENDS_VERIFICATION.search(ai_text):
        return None
    return (
        f"{GUARD_PREFIX} Assisted mode: don't send or promise a verification link or code; "
        "the caller verifies from the application link."
    )


def guard_node(state: AgentState, *, runtime: AgentRuntime) -> dict[str, Any]:
    draft, doubt_unconfirmed = _unconfirm_doubted_fields(state)
    user_text, turn_messages = _current_turn({**state, "draft": draft})
    draft, brands_filled = fill_brands_from_user_message(draft, user_text)
    draft, malls_filled = fill_mentioned_malls(draft, user_text, runtime.master)
    draft_changed = list(doubt_unconfirmed)
    draft_changed.extend(brands_filled)
    if malls_filled:
        draft_changed.append(FieldKey.MALLS.value)
    phase = compute_phase(draft).value
    cards_shown = list(state["cards_shown"])
    guard_retries = state["guard_retries"]
    note: str | None = None

    writer = get_stream_writer()

    ai_text = _last_ai_text(state)
    status_lookup = "get_inquiry_status" in _tools_called(turn_messages)
    # After a follow-on, talking about the earlier (really submitted) inquiry is fine.
    about_earlier = bool(draft.follow_on_of) and (
        str(draft.follow_on_of) in ai_text or "start_follow_on" in _tools_called(turn_messages)
    )
    if guard_retries < 1:
        if (
            draft.reference is None
            and not status_lookup
            and not about_earlier
            and ai_text
            and claims_submission(ai_text)
        ):
            note = (
                f"{GUARD_PREFIX} Do not tell the user the inquiry was submitted. "
                "It is only submitted when a submitted reference ui_event arrives. "
                "Reply again without that claim."
            )
        elif (
            phase == "existing_account"
            and not state.get("assisted")  # the executive chooses on the card instead
            and ai_text
            and not _SIGN_IN_RE.search(ai_text)
        ):
            note = (
                f"{GUARD_PREFIX} This user already has an account. "
                "Reply again, kindly pointing them to Sign In on Tenant Central."
            )
        else:
            note = (
                _assisted_application_link_note(state, draft, turn_messages, cards_shown)
                or _assisted_verification_claim_note(state, ai_text)
                or _brand_reask_note({**state, "draft": draft}, ai_text)
                or _incomplete_bulk_capture_note({**state, "draft": draft}, phase)
                or _incomplete_contact_capture_note(
                    {**state, "draft": draft},
                    draft,
                    user_text,
                    phase,
                )
                or (
                    None
                    if state.get("assisted")  # no verification in assisted mode
                    else _missing_send_verification_note(
                        state,
                        draft,
                        user_text,
                        turn_messages,
                        cards_shown,
                    )
                )
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
