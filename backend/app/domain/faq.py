"""FAQ loading and keyword search."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class FaqEntry(BaseModel):
    id: str
    question: str
    keywords: list[str] = Field(default_factory=list)
    answer: str


class FaqMatch(BaseModel):
    entry: FaqEntry
    score: float


_FAQ_PATH = Path(__file__).resolve().parent.parent / "data" / "faq.json"


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@lru_cache
def load_faq_entries() -> tuple[FaqEntry, ...]:
    raw = json.loads(_FAQ_PATH.read_text(encoding="utf-8"))
    return tuple(FaqEntry.model_validate(item) for item in raw)


def search_faq(query: str, k: int = 2) -> list[FaqEntry]:
    """Return top ``k`` FAQ entries by keyword and token overlap (no external libs)."""
    if not query.strip():
        return []

    query_lower = query.lower()
    query_tokens = _tokenize(query)

    scored: list[FaqMatch] = []
    for entry in load_faq_entries():
        score = 0.0
        haystack = " ".join([entry.question, *entry.keywords, entry.answer]).lower()
        hay_tokens = _tokenize(haystack)

        overlap = query_tokens & hay_tokens
        score += len(overlap) * 2.0

        for keyword in entry.keywords:
            kw = keyword.lower()
            if kw in query_lower or query_lower in kw:
                score += 3.0
            kw_tokens = _tokenize(kw)
            score += len(query_tokens & kw_tokens) * 1.5

        if query_lower in entry.question.lower():
            score += 2.0

        if score > 0:
            scored.append(FaqMatch(entry=entry, score=score))

    scored.sort(key=lambda match: (-match.score, match.entry.id))
    return [match.entry for match in scored[:k]]
