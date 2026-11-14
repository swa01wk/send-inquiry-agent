"""Assisted mode: the executive's chat never talks about verification, codes or documents
(F4 evals CC3: "then we can move on to verification")."""

from __future__ import annotations

import pytest
from app.agent.guard import _assisted_later_steps_note


@pytest.mark.parametrize(
    "reply",
    [
        "I only need the mall now, and then we can move on to verification.",
        "Once that's in, the verification and documents steps will open up.",
        "The caller can upload the profiles later.",
        "They'll get an SMS code.",
    ],
)
def test_later_steps_are_flagged_in_assisted_mode(reply: str) -> None:
    note = _assisted_later_steps_note({"assisted": True}, reply)
    assert note is not None and "Send application link" in note


@pytest.mark.parametrize(
    "reply",
    [
        "Thanks — I've saved Sara's details. Which mall is the caller after?",
        "The application link card is ready: press Send application link.",
        "Please ask for the caller's email and press Check contact on the card.",
        "The caller will verify their email from the link.",
    ],
)
def test_ordinary_assisted_replies_pass(reply: str) -> None:
    assert _assisted_later_steps_note({"assisted": True}, reply) is None


def test_public_chat_is_not_affected() -> None:
    assert _assisted_later_steps_note({}, "Please finish the verification card.") is None
