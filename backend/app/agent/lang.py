"""The chat's language, set by code from what the user types (18 Nov B1 §3.2).

The same test `guard._wrong_language_note` applies: Arabic when the message's letters are
mostly Arabic. An Arabic brand name in an English sentence stays English; a message with no
letters (a number, an email) keeps the language the chat already has.
"""

from __future__ import annotations

import re

ARABIC_LETTERS_RE = re.compile(r"[؀-ۿ]")
LATIN_LETTERS_RE = re.compile(r"[A-Za-z]")
_EMAIL_OR_URL_RE = re.compile(r"\S+@\S+|https?://\S+")


def message_lang(text: str, previous: str = "en") -> str:
    """ "ar" or "en" for a typed message; `previous` when it has no letters to go by."""
    cleaned = _EMAIL_OR_URL_RE.sub(" ", text)
    arabic = len(ARABIC_LETTERS_RE.findall(cleaned))
    latin = len(LATIN_LETTERS_RE.findall(cleaned))
    if arabic == latin:
        return previous if previous in ("en", "ar") else "en"
    return "ar" if arabic > latin else "en"
