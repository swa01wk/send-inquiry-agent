"""Verify mall ids against user text and seeded master data."""

from __future__ import annotations

import re

from app.domain import draft_ops
from app.domain.master import Mall, MasterData
from app.domain.models import FieldKey, InquiryDraft, Source

# "at Red Sea Mall", "in Riyadh Mall A", "at Mall of Arabia"
_MALL_AT_IN_RE = re.compile(
    r"(?:\bat|\bin)\s+"
    r"((?:[A-Za-z0-9][A-Za-z0-9'\-\u0600-\u06FF]*(?:\s+[A-Za-z0-9][A-Za-z0-9'\-\u0600-\u06FF]*)*)\s*Mall(?:\s+[A-Z0-9])?)\b",
    re.IGNORECASE,
)
_MALL_OF_RE = re.compile(
    r"\b(?:at|in)\s+(Mall\s+of\s+[A-Za-z][A-Za-z\s]{1,40})\b",
    re.IGNORECASE,
)
_MALL_STANDALONE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9'\-\s]{1,40}Mall(?:\s+[A-Z0-9])?)\b",
)
_MALLOF_STANDALONE_RE = re.compile(
    r"\b(Mall\s+of\s+[A-Za-z][A-Za-z\s]{1,40})\b",
)

_GENERIC_MALL_LEADERS = frozenset(
    {
        "a",
        "an",
        "the",
        "your",
        "our",
        "my",
        "any",
        "one",
        "this",
        "that",
        "which",
        "every",
        "each",
        "some",
        "another",
    }
)


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _normalize_phrase(text: str) -> str:
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"\bthe\b", " ", lowered).strip()


def _whole_name_pattern(normalised_name: str) -> re.Pattern[str] | None:
    words = _collapse_spaces(normalised_name).split()
    if not words:
        return None
    inner = r"\s+".join(re.escape(word) for word in words)
    return re.compile(rf"\b(?:the\s+)?{inner}\b", re.IGNORECASE)


def _message_mentions_whole_name(user_text: str, name: str) -> bool:
    pattern = _whole_name_pattern(name)
    if pattern is None:
        return False
    msg = _collapse_spaces(user_text)
    return bool(pattern.search(msg))


def _is_plausible_mall_name(phrase: str) -> bool:
    words = phrase.split()
    if not words:
        return False
    if words[0].lower() in _GENERIC_MALL_LEADERS:
        return False
    has_capital = any(word[0].isupper() and word.lower() != "mall" for word in words if word)
    return has_capital


def extract_mall_phrases(user_text: str) -> list[str]:
    """Mall-like phrases the user named (deduped, order preserved). For guard hints only."""
    seen: set[str] = set()
    phrases: list[str] = []
    patterns = (_MALL_AT_IN_RE, _MALL_OF_RE, _MALL_STANDALONE_RE, _MALLOF_STANDALONE_RE)
    for pattern in patterns:
        for match in pattern.finditer(user_text):
            phrase = match.group(1).strip()
            if not _is_plausible_mall_name(phrase) and not phrase.lower().startswith("mall of"):
                continue
            key = _normalize_phrase(phrase)
            if key not in seen:
                seen.add(key)
                phrases.append(phrase)
    return phrases


def phrase_matches_seed_mall(phrase: str, master: MasterData) -> bool:
    normalized = _normalize_phrase(phrase)
    for mall in master.malls:
        seed = _normalize_phrase(mall.name)
        if normalized == seed or normalized in seed or seed in normalized:
            return True
        for alias in mall.aliases:
            alias_norm = _normalize_phrase(alias)
            if normalized == alias_norm or normalized in alias_norm or alias_norm in normalized:
                return True
    return False


def unknown_mall_phrases(user_text: str, master: MasterData) -> list[str]:
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return []
    return [p for p in extract_mall_phrases(user_text) if not phrase_matches_seed_mall(p, master)]


def user_message_mentions_mall(
    user_text: str,
    mall_name: str,
    *,
    aliases: list[str] | None = None,
) -> bool:
    for candidate in (mall_name, *(aliases or [])):
        if _message_mentions_whole_name(user_text, candidate):
            return True
    return False


def _mall_mentioned(user_text: str, mall: Mall) -> bool:
    return user_message_mentions_mall(user_text, mall.name, aliases=mall.aliases)


def mentioned_seed_mall_ids(user_text: str, master: MasterData) -> list[str]:
    """Seed mall ids the user's message names (order stable, deduped)."""
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return []
    seen: set[str] = set()
    ids: list[str] = []
    for mall in master.malls:
        if mall.id in seen:
            continue
        if _mall_mentioned(user_text, mall):
            seen.add(mall.id)
            ids.append(mall.id)
    return ids


def fill_mentioned_malls(
    draft: InquiryDraft,
    user_text: str,
    master: MasterData,
) -> tuple[InquiryDraft, bool]:
    """When malls is empty and the user named seed mall(s), write matching ids as user."""
    raw = draft.fields[FieldKey.MALLS].value
    if isinstance(raw, list) and raw:
        return draft, False
    ids = mentioned_seed_mall_ids(user_text, master)
    if not ids:
        return draft, False
    updated, written, errors = draft_ops.write_fields(
        draft,
        [(FieldKey.MALLS.value, ids, Source.USER)],
        master=master,
    )
    if FieldKey.MALLS.value in written and FieldKey.MALLS.value not in errors:
        return updated, True
    return draft, False


def filter_mall_ids(
    proposed_ids: list[str],
    existing_ids: list[str],
    user_text: str,
    master: MasterData,
) -> tuple[list[str], list[str]]:
    """Return accepted ids and rejected ids (not mentioned and not already selected)."""
    existing = set(existing_ids)
    seed_ids = master.mall_ids()
    accepted: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for mall_id in proposed_ids:
        if mall_id in seen:
            continue
        seen.add(mall_id)
        if mall_id not in seed_ids:
            rejected.append(mall_id)
            continue
        if mall_id in existing:
            accepted.append(mall_id)
            continue
        mall = next(m for m in master.malls if m.id == mall_id)
        if _mall_mentioned(user_text, mall):
            accepted.append(mall_id)
        else:
            rejected.append(mall_id)
    return accepted, rejected
