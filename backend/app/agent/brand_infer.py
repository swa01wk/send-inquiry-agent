"""Infer missing brand_name_en from company name or user message (deterministic)."""

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
_COMPANY_BRAND_PREFIX_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9' \-]{0,60}?)\s+"
    r"(?:Trading|LLC|Ltd|Co\.|Company|Group|Inc|Limited)\b",
    re.IGNORECASE,
)


def _field_text(draft: InquiryDraft, key: FieldKey) -> str | None:
    value = draft.fields[key].value
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _valid_en(candidate: str) -> str | None:
    checked = v.validate_brand_name_en(candidate.strip())
    return checked if isinstance(checked, str) else None


def brand_en_from_company_name(company_name: str) -> str | None:
    match = _COMPANY_BRAND_PREFIX_RE.match(company_name.strip())
    if not match:
        return None
    return _valid_en(match.group(1))


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
    """When brand_name_ar is set but EN is empty, infer EN from message or company."""
    if _field_text(draft, FieldKey.BRAND_NAME_EN):
        return draft, False
    if not _field_text(draft, FieldKey.BRAND_NAME_AR):
        label_ar = extract_arabic_brand_from_message(user_text)
        if label_ar:
            updated = draft.model_copy(deep=True)
            ar_field = draft.fields[FieldKey.BRAND_NAME_AR]
            updated.fields[FieldKey.BRAND_NAME_AR] = ar_field.model_copy(
                update={"value": label_ar, "source": Source.USER, "confirmed": True},
            )
            draft = updated

    candidate = extract_latin_brand_from_message(user_text)
    if not candidate:
        company = _field_text(draft, FieldKey.COMPANY_NAME)
        if company:
            candidate = brand_en_from_company_name(company)

    if not candidate:
        return draft, False

    updated = draft.model_copy(deep=True)
    updated.fields[FieldKey.BRAND_NAME_EN] = draft.fields[FieldKey.BRAND_NAME_EN].model_copy(
        update={"value": candidate, "source": Source.DERIVED, "confirmed": False},
    )
    return updated, True
