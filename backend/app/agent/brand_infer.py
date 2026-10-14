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
# Latin token in a capitalised run directly before an Arabic parenthesis (ASCII \w semantics).
_CAP_WORD_RE = re.compile(r"^[A-Z0-9][A-Za-z0-9'&.-]*$", re.ASCII)
_AR_IN_PAREN_RE = re.compile(
    r"\(([\u0600-\u06FF][\u0600-\u06FF\s'']{0,78}?)\)",
)
_BRAND_EN_FILLER = frozenset(
    {"brand", "our", "my", "we", "the", "called", "named", "it's", "its", "is"},
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


def _strip_brand_en_filler(raw: str) -> str:
    words = raw.strip().split()
    while words and words[0].lower() in _BRAND_EN_FILLER:
        words.pop(0)
    return " ".join(words)


def _en_from_cap_run(raw: str) -> str | None:
    return _valid_en(_strip_brand_en_filler(raw))


def _cap_words_before_paren(text: str, open_paren: int) -> str | None:
    """Up to four capitalised Latin words immediately before ``(``."""
    left = text[:open_paren].rstrip()
    if not left:
        return None
    words = left.split()
    taken: list[str] = []
    for word in reversed(words):
        if len(taken) >= 4:
            break
        if not _CAP_WORD_RE.match(word):
            break
        taken.append(word)
        if word.endswith(".") and len(taken) >= 1:
            taken.pop()
            break
    if not taken:
        return None
    return " ".join(reversed(taken))


def _first_en_ar_paren_pair(user_text: str) -> tuple[str, str] | None:
    for match in _AR_IN_PAREN_RE.finditer(user_text):
        en_raw = _cap_words_before_paren(user_text, match.start())
        if not en_raw:
            continue
        en = _en_from_cap_run(en_raw)
        ar = _valid_ar(match.group(1))
        if en and ar:
            return en, ar
    return None


def extract_arabic_brand_from_message(user_text: str) -> str | None:
    match = _AR_BRAND_LABEL_RE.search(user_text)
    if not match:
        return None
    return _valid_ar(match.group(1))


def extract_latin_brand_from_message(user_text: str) -> str | None:
    pair = _first_en_ar_paren_pair(user_text)
    return pair[0] if pair else None


def user_message_names_brand(user_text: str) -> bool:
    if extract_latin_brand_from_message(user_text) or extract_arabic_brand_from_message(user_text):
        return True
    return _AR_IN_PAREN_RE.search(user_text) is not None


def _write_brand_user(
    draft: InquiryDraft,
    key: FieldKey,
    value: str,
) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    updated.fields[key] = draft.fields[key].model_copy(
        update={"value": value, "source": Source.USER, "confirmed": True},
    )
    return updated


def _write_brand_en_derived(
    draft: InquiryDraft,
    value: str,
) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    key = FieldKey.BRAND_NAME_EN
    updated.fields[key] = draft.fields[key].model_copy(
        update={"value": value, "source": Source.DERIVED, "confirmed": False},
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

    paren_pair = _first_en_ar_paren_pair(user_text)
    if paren_pair:
        en, ar = paren_pair
        if en and not _field_text(updated, FieldKey.BRAND_NAME_EN):
            updated = _write_brand_en_derived(updated, en)
            changed.append(FieldKey.BRAND_NAME_EN.value)
        if ar and not _field_text(updated, FieldKey.BRAND_NAME_AR):
            updated = _write_brand_user(updated, FieldKey.BRAND_NAME_AR, ar)
            changed.append(FieldKey.BRAND_NAME_AR.value)

    ar_label = extract_arabic_brand_from_message(user_text)
    if ar_label and not _field_text(updated, FieldKey.BRAND_NAME_AR):
        updated = _write_brand_user(updated, FieldKey.BRAND_NAME_AR, ar_label)
        changed.append(FieldKey.BRAND_NAME_AR.value)

    if not _field_text(updated, FieldKey.BRAND_NAME_EN):
        ar_field = updated.fields[FieldKey.BRAND_NAME_AR]
        if ar_field.source == Source.USER and _field_text(updated, FieldKey.BRAND_NAME_AR):
            candidate = extract_latin_brand_from_message(user_text)
            if candidate:
                updated = _write_brand_en_derived(updated, candidate)
                changed.append(FieldKey.BRAND_NAME_EN.value)

    return updated, changed


def fill_missing_brand_name_en(
    draft: InquiryDraft,
    user_text: str,
) -> tuple[InquiryDraft, bool]:
    """Backward-compatible wrapper; prefer fill_brands_from_user_message."""
    updated, changed = fill_brands_from_user_message(draft, user_text)
    return updated, FieldKey.BRAND_NAME_EN.value in changed
