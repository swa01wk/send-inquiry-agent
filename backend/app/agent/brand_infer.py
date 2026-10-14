"""Infer missing brand_name_en from user message (deterministic)."""

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


def _field_text(draft: InquiryDraft, key: FieldKey) -> str | None:
    value = draft.fields[key].value
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _valid_en(candidate: str) -> str | None:
    checked = v.validate_brand_name_en(candidate.strip())
    return checked if isinstance(checked, str) else None


def extract_arabic_brand_from_message(user_text: str) -> str | None:
    match = _AR_BRAND_LABEL_RE.search(user_text)
    if not match:
        return None
    phrase = match.group(1).strip()
    if not phrase or not v.ARABIC_RE.search(phrase):
        return None
    checked = v.validate_brand_name_ar(phrase)
    return checked if isinstance(checked, str) else None


def extract_latin_brand_from_message(user_text: str) -> str | None:
    paren = _EN_BEFORE_AR_PAREN_RE.search(user_text)
    if paren:
        found = _valid_en(paren.group(1))
        if found:
            return found
    return None


def fill_missing_brand_name_en(
    draft: InquiryDraft,
    user_text: str,
) -> tuple[InquiryDraft, bool]:
    """When brand_name_ar is user-provided and EN is empty, infer EN from the message only."""
    if _field_text(draft, FieldKey.BRAND_NAME_EN):
        return draft, False
    ar_field = draft.fields[FieldKey.BRAND_NAME_AR]
    if ar_field.source != Source.USER or not _field_text(draft, FieldKey.BRAND_NAME_AR):
        return draft, False

    candidate = extract_latin_brand_from_message(user_text)
    if not candidate:
        return draft, False

    updated = draft.model_copy(deep=True)
    updated.fields[FieldKey.BRAND_NAME_EN] = draft.fields[FieldKey.BRAND_NAME_EN].model_copy(
        update={"value": candidate, "source": Source.USER, "confirmed": True},
    )
    return updated, True
