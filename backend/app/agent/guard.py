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
from app.agent.bundles import still_needed_line
from app.agent.confirm_policy import keys_blocked_from_confirmation
from app.agent.contact_infer import (
    contact_fields_ready,
    message_has_contact_line,
    parse_contact_from_message,
)
from app.agent.cr_question import CR_NUMBER_IN_REPLY, contains_cr_number, cr_question_active
from app.agent.mall_match import (
    fill_mentioned_malls,
    mentioned_seed_mall_ids,
    unknown_mall_phrases,
)
from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.cards import (
    TERMS_CARD_ID,
    VERIFICATION_CARD_ID,
    build_document_upload_card,
    build_mall_picker_card,
    build_quick_replies_card,
    build_review_card,
    build_terms_card,
)
from app.api.channel_cards import basic_info_missing, build_send_link_card
from app.api.schemas import UiCard
from app.domain.fields import document_label
from app.domain.models import NEEDS_CONFIRMATION, DocType, FieldKey, InquiryDraft, Source
from app.domain.rules import compute_phase, contact_verified, remaining_steps
from app.domain.sections import (
    SECTION_LABELS,
    IntakeSection,
    current_section,
    section_done,
    section_rank,
)
from app.domain.summary import build_draft_summary
from app.domain.validation import normalise_digits
from app.policy.config import get_policy

GUARD_PREFIX = "[ui_event] guard:"

# A claim that the inquiry was submitted, e.g. "your inquiry has been submitted",
# "I've sent your inquiry", "your reference number is GEO-…". Plain uses of the word
# "reference" ("for your reference") do not match.
_FALSE_SUBMIT_RE = re.compile(
    r"\b(inquiry|enquiry|application|request)\b[^.!?\n]{0,40}?"
    r"\b(has been|have been|was|is now|is)\s+"
    r"(submitted|sent|received)\b"
    r"|\bI(?:'ve| have)\s+(?:submitted|sent)\s+(?:your|the)\b"
    r"(?!\s+(?:verification|email link|sms|code|one-time))"
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


def _verification_after_proceed_note(
    state: AgentState,
    draft: Any,
    user_text: str,
    turn_messages: list[BaseMessage],
    cards_shown: list[str],
) -> str | None:
    """The applicant from a call-centre link pressed Proceed (the email is verified by the
    link, the mobile isn't): the verification card comes next. Live run 10 Nov, flow 4: the
    model moved on to documents and the mobile was never verified."""
    if not user_text.startswith("[ui_event] basic_info_confirmed"):
        return None
    if state.get("channel") == "existing_tenant" or state.get("assisted"):
        return None  # a signed-in tenant's contact comes from the Cenomi record
    if VERIFICATION_CARD_ID in cards_shown or contact_verified(draft):
        return None
    if not contact_fields_ready(draft) or "send_verification" in _tools_called(turn_messages):
        return None
    return (
        f"{GUARD_PREFIX} The applicant confirmed their details, but the contact isn't verified "
        "yet. Call send_verification before you reply, then point them to the card."
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


_PROFILES_COMING_RE = re.compile(r"\bupload\b[^.?!\n]{0,40}\bprofiles?\b", re.IGNORECASE)


def _profiles_coming(state: AgentState) -> bool:
    """The applicant chose to upload the Company and Brand Profiles (demo feedback §3.7):
    the brand comes from the Brand Profile, so a message without one isn't a missed capture."""
    for message in state.get("messages") or []:
        if not isinstance(message, HumanMessage):
            continue
        text = str(message.content)
        if text.startswith("[ui_event]") or text.startswith(GUARD_PREFIX):
            continue
        if _PROFILES_COMING_RE.search(text):
            return True
    return False


def _v2_documents_card_due(state: AgentState, draft: InquiryDraft) -> bool:
    """Flow v2 (§3.3): the documents card after the terms, or as soon as they choose to
    upload the profiles (they fill Basic Info, demo feedback §3.7)."""
    section = current_section(draft)
    if section is IntakeSection.DOCUMENTS:
        return True
    return section_rank(section) < section_rank(IntakeSection.TERMS) and _profiles_coming(state)


def _terms_card_due(draft: InquiryDraft, cards_shown: list[str]) -> bool:
    """Flow v2 (§3.3, FV15): the terms card once Property Details is done."""
    return (
        draft.intake_flow == "v2"
        and get_policy().flow_v2_intake.terms_before_documents
        and TERMS_CARD_ID not in cards_shown
        and not draft.terms_accepted
        and section_done(draft, IntakeSection.PROPERTY_DETAILS)
        and section_done(draft, IntakeSection.VERIFICATION)
    )


def _v2_mall_picker_city(
    draft: InquiryDraft,
    cards_shown: list[str],
    user_text: str,
    turn_messages: list[BaseMessage],
    master: Any,
) -> str | None:
    """Flow v2 (S11): they named a city or "any mall in <city>" but no mall, and the model
    didn't open the picker. The city to open it for, or None."""
    if draft.intake_flow != "v2" or "malls" in cards_shown:
        return None
    if current_section(draft) is not IntakeSection.PROPERTY_DETAILS:
        return None
    if _field_has_value(draft, FieldKey.MALLS) or "show_mall_picker" in _tools_called(
        turn_messages
    ):
        return None
    if mentioned_seed_mall_ids(user_text, master):
        return None
    lowered = user_text.lower()
    for city in master.cities:
        names = {city.id.lower(), city.label.lower(), (city.label_ar or "").strip()}
        if any(n and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", lowered) for n in names):
            return str(city.id)
    return None


# Rule 8 (flow v2 §3.3): words that show a reply asks about a section.
_SECTION_ASK_RE: dict[IntakeSection, re.Pattern[str]] = {
    IntakeSection.UNIT_AND_CATEGORY: re.compile(
        r"\b(store or (?:an )?office|unit type|what (?:do|does) (?:you|your \w+) sell|"
        r"sales category)\b",
        re.IGNORECASE,
    ),
    IntakeSection.BASIC_INFO: re.compile(
        r"\b(your (?:full )?name|first name|email|mobile|phone number|landline|company name|"
        r"company(?:'s)? address|brand name)\b",
        re.IGNORECASE,
    ),
    IntakeSection.PROPERTY_DETAILS: re.compile(
        r"\b(which malls?|what malls?|mall(?:s)? (?:are you|do you)|lease period|"
        r"how (?:much|big) (?:space|area)|budget|rent)\b",
        re.IGNORECASE,
    ),
    IntakeSection.DOCUMENTS: re.compile(
        r"\b(company profile|brand profile|upload (?:your|the) documents?)\b", re.IGNORECASE
    ),
}


def _questions(text: str) -> list[str]:
    return [q for q in re.split(r"(?<=[.!?])\s+", text) if q.strip().endswith("?")]


def _later_section_ask_note(
    state: AgentState, draft: InquiryDraft, user_text: str, ai_text: str
) -> str | None:
    """Rule 8 (§3.3, self-service flow v2): the reply asks about a later section while an
    earlier one is open → back to the agent once. Not when the user raised that section."""
    if draft.intake_flow != "v2" or state.get("assisted") or not ai_text:
        return None
    current = current_section(draft)
    if current not in (
        IntakeSection.COMPANY_REGISTRATION,
        IntakeSection.UNIT_AND_CATEGORY,
        IntakeSection.BASIC_INFO,
        IntakeSection.VERIFICATION,
        IntakeSection.PROPERTY_DETAILS,
    ):
        return None
    questions = " ".join(_questions(ai_text))
    for section, pattern in _SECTION_ASK_RE.items():
        if section_rank(section) <= section_rank(current) or section_done(draft, section):
            continue
        if pattern.search(questions) and not pattern.search(user_text):
            return (
                f"{GUARD_PREFIX} later_section_ask: ask about {SECTION_LABELS[current]} first "
                f"— it isn't done yet. Save anything they gave early, but don't ask about "
                f"{SECTION_LABELS[section]} yet. Reply again."
            )
    return None


def _v2_missing_verification_note(
    draft: InquiryDraft, turn_messages: list[BaseMessage], cards_shown: list[str]
) -> str | None:
    """Flow v2 (§3.3): once Basic Info is done, verification follows it, before Property
    Details: send_verification must have run."""
    if draft.intake_flow != "v2":
        return None
    if not section_done(draft, IntakeSection.BASIC_INFO) or contact_verified(draft):
        return None
    if VERIFICATION_CARD_ID in cards_shown or draft.email_link_sent_to:
        return None
    if "send_verification" in _tools_called(turn_messages):
        return None
    return (
        f"{GUARD_PREFIX} Basic Info is done: call send_verification before you reply, then "
        "point them to the verification card."
    )


def _documents_card_due(state: AgentState, phase: str) -> bool:
    """Attach the documents card when the user enters the documents phase, or as soon as they
    choose to upload the profiles (demo feedback §3.7). On that path the company and brand
    fields come from the profiles, so the phase can't reach `documents` until they're
    uploaded: waiting for it left the user with nothing to upload with."""
    if phase == "documents":
        return True
    return phase in ("collecting", "verifying") and _profiles_coming(state)


NEW_BRAND_CHOICES = ("I'll type it", "I'll upload the Brand Profile")


def _new_brand_choice_due(
    state: AgentState, draft: Any, user_text: str, turn_messages: list[BaseMessage]
) -> bool:
    """R4: after Proceed, a signed-in tenant is asked for the new brand, typed or filled from
    the Brand Profile. The prompt asks for these chips; when the model skips them the tenant
    has no visible way to choose the upload (re-demo flow 3, 10 Nov). "I'll upload the Brand
    Profile" then brings the documents card (`_documents_card_due`)."""
    return (
        state.get("channel") == "existing_tenant"
        and user_text.startswith("[ui_event] basic_info_confirmed")
        and not _field_has_value(draft, FieldKey.BRAND_NAME_EN)
        and "suggest_replies" not in _tools_called(turn_messages)
    )


def _incomplete_bulk_capture_note(state: AgentState, phase: str) -> str | None:
    user_text, turn_messages = _current_turn(state)
    if phase not in ("gate", "collecting", "verifying") or not _is_bulk_inquiry_message(user_text):
        return None
    if "update_draft" not in _tools_called(turn_messages):
        return None
    draft = state["draft"]
    missing: list[str] = []
    expected: tuple[FieldKey, ...] = (FieldKey.BRAND_NAME_EN, FieldKey.UNIT_TYPE, FieldKey.EMAIL)
    if _profiles_coming(state):
        expected = (FieldKey.UNIT_TYPE, FieldKey.EMAIL)
    for key in expected:
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


_ASKS_ARABIC_RE = re.compile(r"\barabic\b|بالعربي|بالعربية", re.IGNORECASE)


def _brand_from_brand_profile(draft: InquiryDraft) -> bool:
    """`brand_name_en` is still the value the Brand Profile filled (derived, with its evidence)."""
    field = draft.fields[FieldKey.BRAND_NAME_EN]
    label = document_label(DocType.BRAND_PROFILE)
    return field.source == Source.DERIVED and (field.evidence or "").startswith(f"{label}:")


def _brand_reask_note(state: AgentState, ai_text: str) -> str | None:
    if not _reply_asks_for_brand_name(ai_text):
        return None
    draft = state["draft"]
    if (
        _ASKS_ARABIC_RE.search(ai_text)
        and not _field_has_value(draft, FieldKey.BRAND_NAME_AR)
        and _brand_from_brand_profile(draft)
    ):
        # The Brand Profile filled the English name but can't give the Arabic one, so
        # asking for it ("What's the brand name in Arabic?") isn't a re-ask (demo feedback
        # §3.7, R4). When the brand was typed or dictated, the model proposes the Arabic
        # name itself (system prompt), so asking is still a re-ask.
        return None
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


def _cr_number_in_reply_note(state: AgentState, ai_text: str) -> str | None:
    if state.get("assisted") or not ai_text:
        return None
    if not cr_question_active(
        assisted=False,
        channel=state.get("channel"),
        test_scenario=state.get("test_scenario"),
    ):
        return None
    if contains_cr_number(ai_text):
        return CR_NUMBER_IN_REPLY
    return None


def _missed_capture_note(state: AgentState, phase: str) -> str | None:
    user_text, turn_messages = _current_turn(state)
    if not user_text or user_text.startswith("[ui_event]"):
        return None
    called = _tools_called(turn_messages)
    if (
        phase == "gate"
        and _CR_NUMBER_RE.search(user_text)
        and "verify_cr" not in called
        and not cr_question_active(
            assisted=bool(state.get("assisted")),
            channel=state.get("channel"),
            test_scenario=state.get("test_scenario"),
        )
    ):
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


# Talk that sends the user to Submit: "last step", "everything's in", "press Submit",
# "submit when you're ready", "ready to submit", "the review card". Curly apostrophes too.
_SUBMIT_TALK_RE = re.compile(
    r"\b(?:last|final) step\b"
    r"|\beverything(?:['\u2019]s| is)\s+(?:in|done|ready|set|complete)\b"
    r"|\ball set\b"
    r"|\bready to submit\b"
    r"|\b(?:press|click|hit|tap)\s+(?:the\s+)?submit\b"
    r"|\bsubmit\s+(?:it\s+)?(?:when|once|whenever)\s+you(?:['\u2019]re| are)\s+ready\b"
    r"|\breview card\b",
    re.IGNORECASE,
)
# A reply that names what is still open is fine ("once you've opened the email link, the
# review card appears").
_OPEN_STEP_RE: dict[str, re.Pattern[str]] = {
    "verify_email": re.compile(r"\bemail\b|\blink\b", re.IGNORECASE),
    "verify_mobile": re.compile(r"\bcode\b|\bsms\b|\btext message\b", re.IGNORECASE),
    "documents": re.compile(r"\bdocument|\bupload|\bprofile\b", re.IGNORECASE),
}


def _premature_submit_note(state: AgentState, draft: Any, ai_text: str) -> str | None:
    """The reply points to Submit while verification or documents are still open.

    Seen when documents came before the email link (Nov 2026 manual test): the agent said
    "everything's in" and "last step" with the email still unverified.
    """
    if state.get("assisted") or not ai_text or draft.reference:
        return None
    steps = remaining_steps(draft)
    if not steps or "cr" in steps or "fields" in steps:
        return None  # still collecting: other rules apply
    open_steps = [step for step in steps if step in _OPEN_STEP_RE]
    if not open_steps or not _SUBMIT_TALK_RE.search(ai_text):
        return None
    if any(_OPEN_STEP_RE[step].search(ai_text) for step in open_steps):
        return None
    return (
        f"{GUARD_PREFIX} Not ready to submit yet. {still_needed_line(draft)} "
        "Reply again: say briefly what's left and point to that card."
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
    # Straight or curly apostrophe; an adverb may sit before the verb ("I’ve also sent").
    r"\b(?:I(?:['\u2019]m|\s+am)\s+(?:(?:also|now|just)\s+)?sending"
    r"|I(?:['\u2019]ve|\s+have)\s+(?:(?:also|now|just|already)\s+)?sent|sending you)\b"
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


def _assisted_addresses_caller_note(state: AgentState, draft: Any, ai_text: str) -> str | None:
    """Assisted mode: the executive reads every reply, so it must not greet or thank the
    caller by name ("Thanks, Sara"); "Thanks — I've saved Sara's details." is fine."""
    if not state.get("assisted") or not ai_text:
        return None
    first = draft.fields[FieldKey.FIRST_NAME].value
    if not first:
        user_text, _ = _current_turn({**state, "draft": draft})
        parsed = parse_contact_from_message(user_text)
        first = parsed[0] if parsed else None
    if not first:
        return None
    pattern = (
        r"\b(?:thanks|thank you|hi|hello|hey|dear)\b[,!]?\s+"
        + re.escape(str(first).split()[0])
        + r"\b(?![\'\u2019]s)"
    )
    if not re.search(pattern, ai_text, re.IGNORECASE):
        return None
    return (
        f"{GUARD_PREFIX} Assisted mode: you are talking to the executive, not the caller. "
        "Don't greet or thank the caller by name. Reply again starting with "
        f"\"Thanks — I've saved {first}'s details.\" and keep the rest of your reply."
    )


def _assisted_reply_note(state: AgentState, draft: Any, ai_text: str) -> str | None:
    """Both assisted wording rules in one note: the guard retries once, so a reply that
    thanks the caller by name and claims a verification send must fix both at once."""
    notes = [
        note
        for note in (
            _assisted_verification_claim_note(state, ai_text),
            _assisted_addresses_caller_note(state, draft, ai_text),
        )
        if note
    ]
    if not notes:
        return None
    rest = [note.removeprefix(GUARD_PREFIX).strip() for note in notes[1:]]
    return " ".join([notes[0], *rest])


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
                _cr_number_in_reply_note(state, ai_text)
                or _assisted_application_link_note(state, draft, turn_messages, cards_shown)
                or _premature_submit_note(state, draft, ai_text)
                or _assisted_reply_note(state, draft, ai_text)
                or _brand_reask_note({**state, "draft": draft}, ai_text)
                or _incomplete_bulk_capture_note({**state, "draft": draft}, phase)
                or _incomplete_contact_capture_note(
                    {**state, "draft": draft},
                    draft,
                    user_text,
                    phase,
                )
                or _later_section_ask_note(state, draft, user_text, ai_text)
                or (
                    None
                    if state.get("assisted")  # no verification in assisted mode
                    else _v2_missing_verification_note(draft, turn_messages, cards_shown)
                    or _missing_send_verification_note(
                        state,
                        draft,
                        user_text,
                        turn_messages,
                        cards_shown,
                    )
                    or _verification_after_proceed_note(
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

    if _terms_card_due(draft, cards_shown):
        _emit_card(build_terms_card(draft), writer)
        cards_shown.append(TERMS_CARD_ID)

    picker_city = _v2_mall_picker_city(draft, cards_shown, user_text, turn_messages, runtime.master)
    if picker_city is not None:
        _emit_card(build_mall_picker_card(draft, runtime.master, picker_city), writer)
        cards_shown.append("malls")

    documents_due = (
        _v2_documents_card_due(state, draft)
        if draft.intake_flow == "v2"
        else _documents_card_due(state, phase)
    )
    if "documents" not in cards_shown and documents_due:
        card = build_document_upload_card(
            draft,
            runtime.master,
            max_mb=runtime.settings.max_upload_mb,
        )
        _emit_card(card, writer)
        cards_shown.append("documents")

    if _new_brand_choice_due(state, draft, user_text, turn_messages):
        _emit_card(
            build_quick_replies_card([(opt, opt, None, None) for opt in NEW_BRAND_CHOICES]),
            writer,
        )

    if phase == "review" and "review" not in cards_shown:
        card = build_review_card(draft, runtime.master)
        _emit_card(card, writer)
        cards_shown.append("review")
    elif "review" in cards_shown and (
        draft_changed or _CAPTURE_TOOLS & _tools_called(turn_messages)
    ):
        # The review card is a snapshot: a change made in chat re-sends it (same card id,
        # updated in place), as `_review_refresh` does for card actions.
        _emit_card(build_review_card(draft, runtime.master), writer)

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
