"""Infer missing contact fields from user message (deterministic)."""

from __future__ import annotations

import re

from app.domain import draft_ops
from app.domain import validation as v
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft, Source, WriteKey

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)
_PHONE_RE = re.compile(
    r"(?:\+966|966|0)?5\d{8}\b|(?:\+966|966|0)?[1-49]\d{7}\b",
)
_NAME_WORD_RE = re.compile(r"^[\u0600-\u06FFA-Za-z][\u0600-\u06FFA-Za-z'-]*$")


def _field_text(draft: InquiryDraft, key: FieldKey) -> str | None:
    value = draft.fields[key].value
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _name_before_email(text: str, email_start: int) -> tuple[str, str] | None:
    prefix = re.sub(r"[,،]\s*$", "", text[:email_start].strip())
    for sep in ("—", "–"):
        if sep in prefix:
            prefix = prefix.rsplit(sep, 1)[-1].strip()
    words = prefix.split()
    if len(words) < 2:
        return None
    first, last = words[-2], words[-1]
    if not _NAME_WORD_RE.match(first) or not _NAME_WORD_RE.match(last):
        return None
    if not isinstance(v.validate_name(first, code="x", label="First name"), str):
        return None
    if not isinstance(v.validate_name(last, code="x", label="Last name"), str):
        return None
    return first, last


def parse_contact_from_message(user_text: str) -> tuple[str, str, str, str] | None:
    """Return (first_name, last_name, email, phone_raw) when all are present."""
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return None
    normalised = user_text.replace("،", ",")
    email_match = _EMAIL_RE.search(normalised)
    if not email_match:
        return None
    phone_match = _PHONE_RE.search(normalised)
    if not phone_match:
        return None
    email = v.validate_email(email_match.group(0))
    if not isinstance(email, str):
        return None
    phone_raw = phone_match.group(0)
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


def fill_contact_from_user_message(
    draft: InquiryDraft,
    user_text: str,
    *,
    master: MasterData,
) -> tuple[InquiryDraft, list[str]]:
    """Fill empty contact fields from a name / email / phone line."""
    parsed = parse_contact_from_message(user_text)
    if not parsed:
        return draft, []

    first, last, email, phone_raw = parsed
    entries: list[tuple[str, object, Source]] = []
    if not _field_text(draft, FieldKey.FIRST_NAME):
        entries.append((FieldKey.FIRST_NAME.value, first, Source.USER))
    if not _field_text(draft, FieldKey.LAST_NAME):
        entries.append((FieldKey.LAST_NAME.value, last, Source.USER))
    if not _field_text(draft, FieldKey.EMAIL):
        entries.append((FieldKey.EMAIL.value, email, Source.USER))
    has_phone = _field_text(draft, FieldKey.MOBILE) or _field_text(draft, FieldKey.LANDLINE)
    if not has_phone:
        entries.append((WriteKey.CONTACT_NUMBER.value, phone_raw, Source.USER))

    if not entries:
        return draft, []

    updated, written, _errors = draft_ops.write_fields(draft, entries, master=master)
    return updated, written
