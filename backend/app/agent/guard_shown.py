"""Detect whether the agent's reply showed a draft value to the user."""

from __future__ import annotations

import re

from app.domain.models import FieldKey, InquiryDraft


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def value_shown_in_reply(key: FieldKey, value: object, ai_text: str) -> bool:
    if not ai_text.strip() or value is None:
        return False
    if key == FieldKey.BRAND_NAME_EN and isinstance(value, str):
        needle = _normalize_for_match(value)
        hay = _normalize_for_match(ai_text)
        return bool(needle) and needle in hay
    return False


def field_shown_in_reply(key: FieldKey, draft: InquiryDraft, ai_text: str) -> bool:
    field = draft.fields[key]
    return value_shown_in_reply(key, field.value, ai_text)
