"""Live-eval checks that read the agent's wording (scripts/eval_live.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from eval_live import TurnResult, _offers_new_inquiry  # noqa: E402


@pytest.mark.parametrize(
    ("reply", "offered"),
    [
        # Eval 16 Nov, S19 run 3: a correct reply the old check failed.
        (
            "The leasing team has finished this inquiry, and you can raise a new one at any "
            "time with updated documents or for another mall.",
            True,
        ),
        ("You're welcome to start another inquiry whenever you like.", True),
        ("You can submit a new inquiry at any time.", True),
        ("It was rejected because it wasn't a fit for this mall.", False),
    ],
)
def test_offers_new_inquiry(reply: str, offered: bool) -> None:
    assert _offers_new_inquiry([TurnResult(user="Why?", assistant=reply)]) is offered
