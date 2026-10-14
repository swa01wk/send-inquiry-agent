"""Infer missing brand fields from user message (deterministic)."""

from __future__ import annotations

import re

from app.domain import validation as v
from app.domain.models import FieldKey, InquiryDraft, Source

_AR_BRAND_LABEL_RE = re.compile(
    r"(?:اسم\s+ال(?:علامة|براند)|العلامة(?:\s+التجارية)?)\s*[:،]?\s*"
    r"([\u0600-\u06FF][\u0600-\u06FF\s'']{0,78}?)"
    r"(?=\s*[،,.]|$|\s+(?:كشك|متجر|مطعم|قهوة|في|at|in\b))",
)
_EN_BEFORE_AR_PAREN_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9' \-]{0,78}?)\s*\([\u0600-\u06FF]",
)
_EN_AR_PAREN_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9' \-]{0,78}?)\s*\(([\u0600-\u06FF][\u0600-\u06FF\s'']{0,78}?)\)",
)


def _field_text(draft: InquiryDraft, key: FieldKey) -> str | None:
    value = draft.fields[key].value
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _valid_en(candidate: str) -> str | None:
    checked = v.validate_brand_name_en(candidate.strip())
    return checked if isinstance(checked, str) else None


def _valid_ar(candidate: str) -> str | None:
    phrase = candidate.strip()
    if not phrase or not v.ARABIC_RE.search(phrase):
        return None
    checked = v.validate_brand_name_ar(phrase)
    return checked if isinstance(checked, str) else None


def extract_arabic_brand_from_message(user_text: str) -> str | None:
    match = _AR_BRAND_LABEL_RE.search(user_text)
    if not match:
        return None
    return _valid_ar(match.group(1))


def extract_latin_brand_from_message(user_text: str) -> str | None:
    paren = _EN_BEFORE_AR_PAREN_RE.search(user_text)
    if paren:
        found = _valid_en(paren.group(1))
        if found:
            return found
    return None


def user_message_names_brand(user_text: str) -> bool:
    if extract_latin_brand_from_message(user_text) or extract_arabic_brand_from_message(user_text):
        return True
    return _EN_AR_PAREN_RE.search(user_text) is not None


def _write_brand(
    draft: InquiryDraft,
    key: FieldKey,
    value: str,
) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    updated.fields[key] = draft.fields[key].model_copy(
        update={"value": value, "source": Source.USER, "confirmed": True},
    )
    return updated


def fill_brands_from_user_message(
    draft: InquiryDraft,
    user_text: str,
) -> tuple[InquiryDraft, list[str]]:
    """Fill empty brand_name_en/ar from explicit patterns in the user's message."""
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return draft, []

    updated = draft
    changed: list[str] = []

    paren = _EN_AR_PAREN_RE.search(user_text)
    if paren:
        en = _valid_en(paren.group(1))
        ar = _valid_ar(paren.group(2))
        if en and not _field_text(updated, FieldKey.BRAND_NAME_EN):
            updated = _write_brand(updated, FieldKey.BRAND_NAME_EN, en)
            changed.append(FieldKey.BRAND_NAME_EN.value)
        if ar and not _field_text(updated, FieldKey.BRAND_NAME_AR):
            updated = _write_brand(updated, FieldKey.BRAND_NAME_AR, ar)
            changed.append(FieldKey.BRAND_NAME_AR.value)

    ar_label = extract_arabic_brand_from_message(user_text)
    if ar_label and not _field_text(updated, FieldKey.BRAND_NAME_AR):
        updated = _write_brand(updated, FieldKey.BRAND_NAME_AR, ar_label)
        changed.append(FieldKey.BRAND_NAME_AR.value)

    if not _field_text(updated, FieldKey.BRAND_NAME_EN):
        ar_field = updated.fields[FieldKey.BRAND_NAME_AR]
        if ar_field.source == Source.USER and _field_text(updated, FieldKey.BRAND_NAME_AR):
            candidate = extract_latin_brand_from_message(user_text)
            if candidate:
                updated = _write_brand(updated, FieldKey.BRAND_NAME_EN, candidate)
                changed.append(FieldKey.BRAND_NAME_EN.value)

    return updated, changed


def fill_missing_brand_name_en(
    draft: InquiryDraft,
    user_text: str,
) -> tuple[InquiryDraft, bool]:
    """Backward-compatible wrapper; prefer fill_brands_from_user_message."""
    updated, changed = fill_brands_from_user_message(draft, user_text)
    return updated, FieldKey.BRAND_NAME_EN.value in changed
