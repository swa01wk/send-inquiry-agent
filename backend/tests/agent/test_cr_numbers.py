"""CR numbers in the public chat (flow v2 §3.2, I8): the scrubber, invariant I8 and the
guard note. The 4 Nov "Do you have a CR?" question was removed with flow v2."""

from __future__ import annotations

import pytest
from app.agent.cr_question import CR_REMOVED, contains_cr_number, scrub_cr_numbers
from app.agent.invariants import TurnContext, check_turn
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source

# ---- scrubber -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("my CR is 1010000000", f"my CR is {CR_REMOVED}"),
        ("CR: ١٠١٠١٢٣٤٥٦ thanks", f"CR: {CR_REMOVED} thanks"),  # Arabic-Indic digits
        ("two: 1010123456, 1010222222", f"two: {CR_REMOVED}, {CR_REMOVED}"),
    ],
)
def test_scrub_removes_cr_numbers(text: str, expected: str) -> None:
    scrubbed, found = scrub_cr_numbers(text)
    assert found
    assert scrubbed == expected
    assert not contains_cr_number(scrubbed)


@pytest.mark.parametrize(
    "text",
    [
        "call me on 0551234567",  # Saudi mobile, starts with 0
        "+966551234567",  # international number
        "SA0380000000608010167519",  # IBAN-like digit run
        "about 30 sqm, up to 250,000 SAR",
        "no CR yet",
    ],
)
def test_scrub_leaves_other_numbers(text: str) -> None:
    scrubbed, found = scrub_cr_numbers(text)
    assert not found
    assert scrubbed == text


# ---- I8 and the guard -------------------------------------------------------------


def test_i8_flags_cr_numbers_and_registry_details() -> None:
    ctx = TurnContext(assistant_text="Your CR 1010123456 is on file.", flow_v2_intake=True)
    assert "I8" in [v.invariant for v in check_turn(ctx)]
    ctx = TurnContext(
        assistant_text="Thanks! Bean Street Trading Co. is registered.", flow_v2_intake=True
    )
    assert "I8" in [v.invariant for v in check_turn(ctx)]
    ctx = TurnContext(
        assistant_text="ok",
        card_text='{"company": "King Fahd Road, Al Olaya, Riyadh"}',
        flow_v2_intake=True,
    )
    assert "I8" in [v.invariant for v in check_turn(ctx)]


def test_i8_allows_what_the_applicant_typed() -> None:
    draft, _w, errors = write_fields(
        new_inquiry_draft(),
        [(FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.USER)],
        master=load_master_data(),
    )
    assert not errors
    ctx = TurnContext(
        assistant_text="Thanks, Bean Street Trading Co. it is.",
        draft_after=draft,
        flow_v2_intake=True,
    )
    assert all(v.invariant != "I8" for v in check_turn(ctx))


def test_i8_off_outside_the_public_page() -> None:
    ctx = TurnContext(assistant_text="CR 1010123456 checked.", flow_v2_intake=False)
    assert all(v.invariant != "I8" for v in check_turn(ctx))


def test_guard_note_when_reply_contains_a_cr_number() -> None:
    from app.agent.guard import _cr_number_in_reply_note
    from app.agent.state import initial_agent_state

    draft = new_inquiry_draft().model_copy(update={"intake_flow": "v2"})
    state = initial_agent_state(session_id="g-cr", draft=draft, phase="gate")
    state["channel"] = "self_service"
    note = _cr_number_in_reply_note(state, "Thanks — I found CR 1010123456 on file.")
    assert note is not None
    assert "cr_number_in_reply" in note


def test_guard_note_off_outside_the_v2_public_chat() -> None:
    from app.agent.guard import _cr_number_in_reply_note
    from app.agent.state import initial_agent_state

    state = initial_agent_state(session_id="g-cr1", draft=new_inquiry_draft(), phase="gate")
    state["channel"] = "self_service"
    assert _cr_number_in_reply_note(state, "CR 1010123456 checked.") is None
