"""Guard rule 9 `_third_person_team` (18 Nov B1, N2, NG4): the agent is the leasing team.

"our leasing team" and "the leasing team will" go back once; "leasing" alone, or "the
leasing team" without "will", is fine. Self-service and case replies; not staff chats.
"""

from __future__ import annotations

import pytest
from app.agent.eval_checks import speaks_of_leasing_team_in_third_person
from app.agent.guard import GUARD_PREFIX, third_person_team_note


@pytest.mark.parametrize(
    "reply",
    [
        "Who should our leasing team contact?",
        "Our Leasing Team will review it.",
        "Thanks! The leasing team will give the final approval.",
        "سيتواصل معك فريق التأجير لدينا قريبًا.",
    ],
)
def test_third_person_replies_go_back(reply: str) -> None:
    note = third_person_team_note(reply)
    assert note is not None and note.startswith(GUARD_PREFIX)
    assert "third_person_team" in note
    assert speaks_of_leasing_team_in_third_person(reply)


@pytest.mark.parametrize(
    "reply",
    [
        "We'll contact you once we've reviewed it.",
        "Leasing in Riyadh Mall A starts at 30 sqm.",
        "It's with the leasing team for review.",
        "",
    ],
)
def test_first_person_replies_pass(reply: str) -> None:
    assert third_person_team_note(reply) is None
    assert not speaks_of_leasing_team_in_third_person(reply)
