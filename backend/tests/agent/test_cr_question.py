"""The public page's CR question, deterministic parts (demo feedback §3.1, D1–D3)."""

from __future__ import annotations

import pytest
from app.agent.bundles import next_bundle_hint
from app.agent.cr_question import (
    CR_REMOVED,
    apply_cr_answer,
    contains_cr_number,
    cr_question_active,
    scrub_cr_numbers,
)
from app.agent.invariants import TurnContext, check_turn
from app.agent.tools import ASSISTED_TOOLS, TOOLS, record_cr_answer, verify_cr
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.policy.config import get_policy, use_policy
from langgraph.types import Command
from tests.agent.conftest import make_tool_runtime


@pytest.fixture
def ask_first():
    with use_policy(get_policy().with_changes(public_cr_check="ask_then_sign_in")):
        yield


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


# ---- policy and channel ---------------------------------------------------------------


def test_lookup_policy_keeps_todays_behaviour() -> None:
    assert get_policy().public_cr_check == "lookup"
    assert not cr_question_active(assisted=False, channel="self_service")


def test_question_only_on_the_public_channel(ask_first) -> None:
    assert cr_question_active(assisted=False, channel="self_service")
    assert cr_question_active(assisted=False, channel=None)
    assert not cr_question_active(assisted=True, channel="assisted")  # D3: staff keep it
    assert not cr_question_active(assisted=False, channel="existing_tenant")


def test_tool_lists() -> None:
    assert "record_cr_answer" in {t.name for t in TOOLS}
    assisted = {t.name for t in ASSISTED_TOOLS}
    assert "record_cr_answer" not in assisted
    assert "verify_cr" in assisted  # D3


# ---- answers --------------------------------------------------------------------------


def test_answer_yes_and_no() -> None:
    yes = apply_cr_answer(new_inquiry_draft(), True)
    no = apply_cr_answer(new_inquiry_draft(), False)
    assert yes is not None and yes.draft.cr_status == "existing"
    assert yes.note == "[ui_event] cr_answer yes"
    assert no is not None and no.draft.cr_status == "skipped"
    assert no.note == "[ui_event] cr_answer no"
    assert apply_cr_answer(no.draft, True) is None  # already answered


def test_record_cr_answer_no(ask_first, agent_runtime, base_state, stream_events) -> None:
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = record_cr_answer.invoke({"has_cr": False, "state": base_state, "runtime": runtime})
    assert isinstance(result, Command)
    assert result.update["draft"].cr_status == "skipped"
    cards = [e["data"] for e in events if e.get("type") == "ui_card"]
    assert [c["card_type"] for c in cards] == ["cr_question"]
    assert cards[0]["payload"]["answered"] == "no"


def test_record_cr_answer_yes_shows_sign_in(
    ask_first, agent_runtime, base_state, stream_events
) -> None:
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = record_cr_answer.invoke({"has_cr": True, "state": base_state, "runtime": runtime})
    assert result.update["draft"].cr_status == "existing"
    cards = {e["data"]["card_type"]: e["data"] for e in events if e.get("type") == "ui_card"}
    assert cards["sign_in_prompt"]["payload"]["sign_in_url"].endswith("/tenant")
    audit = agent_runtime.services.audit.events("test-session")
    redirected = [e for e in audit if e["type"] == "inquiry_redirected"]
    assert redirected and redirected[-1]["payload"]["reason"] == "has_cr"


def test_record_cr_answer_unused_under_lookup(agent_runtime, base_state, stream_events) -> None:
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = record_cr_answer.invoke({"has_cr": True, "state": base_state, "runtime": runtime})
    assert result.update["draft"].cr_status == "unknown"
    assert not events


def test_verify_cr_is_off_on_the_public_page(
    ask_first, agent_runtime, base_state, stream_events
) -> None:
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = verify_cr.invoke({"cr_number": "1010123456", "state": base_state, "runtime": runtime})
    draft = result.update["draft"]
    assert draft.cr_status == "unknown"
    assert draft.fields[FieldKey.COMPANY_NAME].value is None  # nothing pulled from the registry
    assert not events
    tool_text = str(result.update["messages"][-1].content)
    assert "1010123456" not in tool_text


def test_hint_asks_the_question_not_the_number(ask_first) -> None:
    hint = next_bundle_hint(new_inquiry_draft(), assisted=False)
    assert "has a CR" in hint
    assert "CR number" not in hint.replace("Never ask for the CR number", "")


# ---- invariant I8 ---------------------------------------------------------------------


def test_i8_flags_cr_numbers_and_registry_details() -> None:
    ctx = TurnContext(assistant_text="Your CR 1010123456 is on file.", public_cr_question=True)
    assert "I8" in [v.invariant for v in check_turn(ctx)]
    ctx = TurnContext(
        assistant_text="Thanks! Bean Street Trading Co. is registered.", public_cr_question=True
    )
    assert "I8" in [v.invariant for v in check_turn(ctx)]
    ctx = TurnContext(
        assistant_text="ok",
        card_text='{"company": "King Fahd Road, Al Olaya, Riyadh"}',
        public_cr_question=True,
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
        public_cr_question=True,
    )
    assert all(v.invariant != "I8" for v in check_turn(ctx))


def test_i8_off_outside_the_public_page() -> None:
    ctx = TurnContext(assistant_text="CR 1010123456 checked.", public_cr_question=False)
    assert all(v.invariant != "I8" for v in check_turn(ctx))
