"""Detect contact lines in user messages (deterministic, detection only)."""

from __future__ import annotations

import re

from app.domain import validation as v
from app.domain.models import FieldKey, InquiryDraft

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
# Ten-digit CR numbers, not local mobiles (05XXXXXXXX).
_CR_IN_TEXT_RE = re.compile(r"(?<!\d)(?!05)\d{10}(?!\d)")
_VAT_IN_TEXT_RE = re.compile(r"(?<!\d)3\d{13}3(?!\d)")
_PHONE_CANDIDATE_RE = re.compile(
    # International form for any country but Saudi (+971 50 123 4567, 0044…)
    r"(?<![\w+])(?:\+|00)(?!966)[1-9](?:[\s-]?\d){7,14}(?!\d)"
    # Saudi mobiles and landlines, local or +966 form
    r"|(?<!\d)(?:\+966|966|0)?5\d{8}(?!\d)|(?<!\d)(?:\+966|966|0)?[1-49]\d{7}(?!\d)",
)
_NAME_WORD_RE = re.compile(r"^[\u0600-\u06FFA-Za-z][\u0600-\u06FFA-Za-z'-]*$")
_NAME_FILLER = frozenset(
    {
        "at",
        "me",
        "is",
        "contact",
        "email",
        "reach",
        "name",
        "my",
        "i'm",
        "im",
        "this",
    },
)


def _field_text(draft: InquiryDraft, key: FieldKey) -> str | None:
    value = draft.fields[key].value
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _long_digit_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (_CR_IN_TEXT_RE, _VAT_IN_TEXT_RE):
        for match in pattern.finditer(text):
            spans.append(match.span())
    return spans


def _span_inside_long_digits(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    for span_start, span_end in spans:
        if start >= span_start and end <= span_end:
            return True
    return False


def _find_phone_raw(text: str) -> str | None:
    spans = _long_digit_spans(text)
    for match in _PHONE_CANDIDATE_RE.finditer(text):
        if _span_inside_long_digits(match.start(), match.end(), spans):
            continue
        return match.group(0)
    return None


def _is_name_word(word: str) -> bool:
    if not _NAME_WORD_RE.match(word):
        return False
    if word[0].isascii() and not word[0].isupper():
        return False
    return True


def _name_before_email(text: str, email_start: int) -> tuple[str, str] | None:
    prefix = re.sub(r"[,،]\s*$", "", text[:email_start].strip())
    for sep in ("—", "–", "/"):
        if sep in prefix:
            prefix = prefix.rsplit(sep, 1)[-1].strip()
    words = prefix.split()
    name_words: list[str] = []
    for word in reversed(words):
        lowered = word.lower().strip(".,،")
        if lowered in _NAME_FILLER:
            if name_words:
                break
            continue
        if not _is_name_word(word.strip(".,،")):
            if name_words:
                break
            continue
        name_words.append(word.strip(".,،"))
    if not name_words:
        return None
    name_words.reverse()
    if len(name_words) < 2:
        return None
    first = name_words[0]
    last = " ".join(name_words[1:])
    if not isinstance(v.validate_name(first, code="x", label="First name"), str):
        return None
    if not isinstance(v.validate_name(last, code="x", label="Last name"), str):
        return None
    return first, last


def parse_contact_from_message(user_text: str) -> tuple[str, str, str, str] | None:
    """Return (first_name, last_name, email, phone_raw) when all are present."""
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return None
    # Arabic-Indic digits count like any others (L3 §3.10).
    normalised = v.normalise_digits(user_text).replace("،", ",")
    email_match = _EMAIL_RE.search(normalised)
    if not email_match:
        return None
    phone_raw = _find_phone_raw(normalised)
    if not phone_raw:
        return None
    email = v.validate_email(email_match.group(0))
    if not isinstance(email, str):
        return None
    if isinstance(v.classify_contact_number(phone_raw), v.ValidationError):
        return None
    names = _name_before_email(normalised, email_match.start())
    if not names:
        return None
    return names[0], names[1], email, phone_raw


def message_has_contact_line(user_text: str) -> bool:
    return parse_contact_from_message(user_text) is not None


def contact_fields_ready(draft: InquiryDraft) -> bool:
    for key in (FieldKey.FIRST_NAME, FieldKey.LAST_NAME, FieldKey.EMAIL):
        if not _field_text(draft, key):
            return False
    return bool(_field_text(draft, FieldKey.MOBILE) or _field_text(draft, FieldKey.LANDLINE))
