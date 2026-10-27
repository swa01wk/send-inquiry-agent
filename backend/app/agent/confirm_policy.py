"""Rules for when derived/verified fields must stay unconfirmed (L3 §3.10).

A derived or verified value is confirmed only when the user accepts it. When the user
doubts a value ("not sure about the category", «مو متأكد من الفئة»), that field must not
be confirmed this turn, and the guard un-confirms it if the agent already did.

Doubt is recognised in English and Arabic, and for every field the agent can derive or
prefill, not only unit type and sales category. The doubt phrase and the field may come
in either order ("not sure about the category" / "the category, not sure").
"""

from __future__ import annotations

import re

from app.domain.models import FieldKey
from app.domain.validation import normalise_digits

_EN_DOUBT = (
    r"not\s+(?:so\s+|too\s+|100%\s+)?sure|unsure|not\s+certain|don'?t\s+know|do\s+not\s+know"
    r"|maybe\s+wrong|might\s+be\s+wrong|could\s+be\s+wrong|hmm+\b|doubt"
)
# Gulf, Levantine, Egyptian and Modern Standard Arabic ways of saying "not sure" / "maybe wrong".
_AR_DOUBT = (
    r"مو\s*متأكد|مو\s*متاكد|مش\s*متأكد|مش\s*متاكد|لست\s*متأكد|لست\s*متاكد|غير\s*متأكد"
    r"|غير\s*متاكد|ما\s*أدري|ما\s*ادري|مدري|لا\s*أعرف|لا\s*اعرف|ما\s*أعرف|ما\s*اعرف"
    r"|يمكن\s*غلط|ممكن\s*غلط|مو\s*أكيد|مو\s*اكيد|مش\s*أكيد|مش\s*اكيد|أشك|اشك"
)
_DOUBT_RE = re.compile(rf"(?:{_EN_DOUBT}|{_AR_DOUBT})", re.IGNORECASE)

# Words that name each field, English (whole words) then Arabic (substrings, so prefixes
# such as ال / بال / و still match).
_FIELD_WORDS: dict[FieldKey, tuple[str, str]] = {
    FieldKey.SALES_CATEGORY: (r"categor\w*|sector", r"الفئة|فئة|الفئه|فئه|التصنيف|تصنيف|القطاع"),
    FieldKey.UNIT_TYPE: (
        r"unit\s+type|type\s+of\s+(?:unit|space)|kind\s+of\s+space|specialty|kiosk|store"
        r"|inline|shop\s+type",
        r"نوع\s*الوحدة|نوع\s*الوحده|الوحدة|الوحده|كشك|نوع\s*المحل|نوع\s*المساحة",
    ),
    FieldKey.BRAND_NAME_AR: (
        r"arabic\s+(?:brand\s+)?name|arabic\s+spelling|name\s+in\s+arabic",
        r"الاسم\s*العربي|الاسم\s*بالعربي|اسم\s*العلامة\s*بالعربي|بالعربي",
    ),
    FieldKey.BRAND_NAME_EN: (
        r"english\s+(?:brand\s+)?name|brand\s+name|name\s+in\s+english",
        r"الاسم\s*الإنجليزي|الاسم\s*الانجليزي|بالإنجليزي|بالانجليزي|اسم\s*العلامة",
    ),
    FieldKey.COMPANY_NAME: (
        r"company\s+name|registered\s+name|legal\s+name",
        r"اسم\s*الشركة|اسم\s*الشركه|اسم\s*المؤسسة",
    ),
    FieldKey.COMPANY_ADDRESS: (
        r"(?:company\s+)?address",
        r"العنوان|عنوان\s*الشركة|عنوان\s*الشركه",
    ),
    FieldKey.MALLS: (r"mall|location|branch", r"المول|مول|الموقع"),
    FieldKey.AREA_MIN: (r"area|size|sqm|square\s+met", r"المساحة|المساحه|مساحة"),
    FieldKey.AREA_MAX: (r"area|size|sqm|square\s+met", r"المساحة|المساحه|مساحة"),
    FieldKey.RENT_MIN: (r"rent|budget", r"الإيجار|الايجار|إيجار|ايجار|الميزانية"),
    FieldKey.RENT_MAX: (r"rent|budget", r"الإيجار|الايجار|إيجار|ايجار|الميزانية"),
    FieldKey.RENT_PERIOD: (r"rent\s+period|per\s+(?:month|year)", r"فترة\s*الإيجار|شهري|سنوي"),
    FieldKey.LEASE_PERIOD: (r"lease|contract\s+length|term", r"مدة\s*العقد|العقد|مدة\s*الإيجار"),
    FieldKey.VAT_NUMBER: (r"vat", r"الضريبي|ضريبة|الضريبة"),
    FieldKey.NATIONAL_ADDRESS: (r"national\s+address", r"العنوان\s*الوطني"),
}

# How far apart the doubt phrase and the field word may be (characters, same sentence).
_GAP = 40
_SENTENCE_END = re.compile(r"[.!?؟\n]")


def _field_pattern(english: str, arabic: str) -> str:
    return rf"(?:\b(?:{english})\b|(?:{arabic}))"


_FIELD_RES: dict[FieldKey, re.Pattern[str]] = {
    key: re.compile(_field_pattern(en, ar), re.IGNORECASE) for key, (en, ar) in _FIELD_WORDS.items()
}
_ANY_FIELD_RE = re.compile(
    "|".join(_field_pattern(en, ar) for en, ar in _FIELD_WORDS.values()), re.IGNORECASE
)


def _matches(window: str) -> list[tuple[int, int, FieldKey]]:
    found: list[tuple[int, int, FieldKey]] = []
    for key, pattern in _FIELD_RES.items():
        for match in pattern.finditer(window):
            found.append((match.start(), match.end(), key))
    return found


def _nearest_after(window: str) -> set[FieldKey]:
    """Keys named first after the doubt phrase (longest name wins at the same spot)."""
    found = _matches(window)
    if not found:
        return set()
    first = min(start for start, _end, _key in found)
    at_first = [(end, key) for start, end, key in found if start == first]
    longest = max(end for end, _key in at_first)
    return {key for end, key in at_first if end == longest}


def _nearest_before(window: str) -> set[FieldKey]:
    """Keys named last before the doubt phrase (longest name wins at the same spot)."""
    found = _matches(window)
    if not found:
        return set()
    last = max(end for _start, end, _key in found)
    at_last = [(start, key) for start, end, key in found if end == last]
    earliest = min(start for start, _key in at_last)
    return {key for start, key in at_last if start == earliest}


def _doubted_keys(text: str) -> set[FieldKey]:
    keys: set[FieldKey] = set()
    for doubt in _DOUBT_RE.finditer(text):
        after = text[doubt.end() : doubt.end() + _GAP]
        cut = _SENTENCE_END.search(after)
        if cut:
            after = after[: cut.start()]
        named = _nearest_after(after)
        if not named:
            before = text[max(0, doubt.start() - _GAP) : doubt.start()]
            stops = list(_SENTENCE_END.finditer(before))
            if stops:
                before = before[stops[-1].end() :]
            named = _nearest_before(before)
        keys |= named
    return keys


# A short message that only expresses doubt ("hmm not sure", «مو متأكد») doubts whatever
# the agent just asked the user to confirm.
GENERAL_DOUBT_MAX_CHARS = 60


def key_shown_on_earlier_turn(
    key: str,
    confirm_card_keys: dict[str, list[str]],
    confirm_card_turns: dict[str, int],
    turn_index: int,
) -> bool:
    """True if the key was on a confirm card emitted before the current user turn."""
    for card_id, listed in confirm_card_keys.items():
        if key not in listed:
            continue
        shown_turn = confirm_card_turns.get(card_id)
        if shown_turn is not None and shown_turn < turn_index:
            return True
    return False


def _user_text(user_text: str) -> str | None:
    stripped = normalise_digits(user_text).strip()
    if not stripped or stripped.startswith("[ui_event]"):
        return None
    return stripped


def keys_blocked_from_confirmation(user_text: str) -> frozenset[str]:
    """Field keys the user explicitly doubted; do not confirm these this turn."""
    stripped = _user_text(user_text)
    if stripped is None:
        return frozenset()
    return frozenset(key.value for key in _doubted_keys(stripped))


def expresses_general_doubt(user_text: str) -> bool:
    """A short message of doubt that names no field ("hmm, not sure", «مو متأكد»).

    It applies to whatever the agent just asked about, so nothing is confirmed this turn.
    The guard never un-confirms on general doubt (it can't tell which value is meant).
    """
    stripped = _user_text(user_text)
    if stripped is None or len(stripped) > GENERAL_DOUBT_MAX_CHARS:
        return False
    return _DOUBT_RE.search(stripped) is not None and _ANY_FIELD_RE.search(stripped) is None
