"""Rules for when derived/verified fields must stay unconfirmed."""

from __future__ import annotations

import re

from app.domain.models import FieldKey

_CATEGORY_DOUBT_RE = re.compile(
    r"(?:not\s+sure|unsure|not\s+certain|don'?t\s+know|maybe\s+wrong|hmm\b)"
    r"[^.!?\n]{0,40}\bcategor",
    re.IGNORECASE,
)
_UNIT_DOUBT_RE = re.compile(
    r"(?:not\s+sure|unsure|not\s+certain|don'?t\s+know|maybe\s+wrong|hmm\b)"
    r"[^.!?\n]{0,40}\b(?:unit\s+type|kind\s+of\s+space|specialty|kiosk|store)\b",
    re.IGNORECASE,
)


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


def keys_blocked_from_confirmation(user_text: str) -> frozenset[str]:
    """Field keys the user has not accepted; do not confirm these this turn."""
    stripped = user_text.strip()
    if not stripped or stripped.startswith("[ui_event]"):
        return frozenset()

    blocked: set[str] = set()
    if _CATEGORY_DOUBT_RE.search(stripped):
        blocked.add(FieldKey.SALES_CATEGORY.value)
    if _UNIT_DOUBT_RE.search(stripped):
        blocked.add(FieldKey.UNIT_TYPE.value)
    return frozenset(blocked)
