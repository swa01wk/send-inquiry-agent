"""Match user mall names against seeded master data."""

from __future__ import annotations

import re

from app.domain.master import MasterData

# "at Red Sea Mall", "in Riyadh Mall A"
_MALL_AT_IN_RE = re.compile(
    r"(?:\bat|\bin)\s+"
    r"((?:[A-Za-z0-9][A-Za-z0-9'\-\u0600-\u06FF]*(?:\s+[A-Za-z0-9][A-Za-z0-9'\-\u0600-\u06FF]*)*)\s*Mall(?:\s+[A-Z0-9])?)\b",
    re.IGNORECASE,
)
# Standalone "Red Sea Mall" when no at/in capture
_MALL_STANDALONE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9'\-\s]{1,40}Mall(?:\s+[A-Z0-9])?)\b",
)


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_mall_phrases(user_text: str) -> list[str]:
    """Mall-like phrases the user named (deduped, order preserved)."""
    seen: set[str] = set()
    phrases: list[str] = []
    for match in _MALL_AT_IN_RE.finditer(user_text):
        phrase = match.group(1).strip()
        key = _normalize_phrase(phrase)
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    for match in _MALL_STANDALONE_RE.finditer(user_text):
        phrase = match.group(1).strip()
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
    return False


def unmatched_mall_phrases(user_text: str, master: MasterData) -> list[str]:
    if not user_text.strip() or user_text.startswith("[ui_event]"):
        return []
    return [p for p in extract_mall_phrases(user_text) if not phrase_matches_seed_mall(p, master)]
