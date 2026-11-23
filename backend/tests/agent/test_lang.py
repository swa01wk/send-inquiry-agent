"""The chat's language from what the user types (18 Nov B1 §3.2)."""

from __future__ import annotations

import pytest
from app.agent.lang import message_lang


@pytest.mark.parametrize(
    ("text", "previous", "want"),
    [
        ("we do coffee and breakfast", "en", "en"),
        ("نقدم القهوة والفطور", "en", "ar"),
        ("Our brand is بين ستريت", "en", "en"),
        ("سارة علي، العلامة Bean Street", "en", "ar"),
        ("0501234567", "ar", "ar"),
        ("sara@beanstreet.example", "ar", "ar"),
        ("", "en", "en"),
        ("ok", "ar", "en"),
    ],
)
def test_message_lang(text: str, previous: str, want: str) -> None:
    assert message_lang(text, previous) == want
