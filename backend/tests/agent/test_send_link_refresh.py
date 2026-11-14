"""Assisted mode: the Send application link card follows the draft once shown (F4 evals:
the card stayed "not ready" after the basic info came in, so the link couldn't be sent)."""

from __future__ import annotations

from app.agent.runtime import AgentRuntime
from app.agent.tools import _refresh_send_link_card
from app.api.channel_cards import SEND_LINK_CARD_ID
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source, new_inquiry_draft
from tests.agent.conftest import make_tool_runtime
from tests.domain.conftest import fill_minimal_collectible


def _complete_draft(base_state):
    draft = fill_minimal_collectible(base_state["draft"], load_master_data())
    draft.cr_status = "new"
    draft.fields[FieldKey.EMAIL].value = "huda.saleh@oasiscoffee.example"
    draft.fields[FieldKey.EMAIL].source = Source.STAFF
    return draft


def _cards(events):
    return [e["data"] for e in events if e["type"] == "ui_card"]


def test_shown_card_turns_ready_when_basic_info_completes(
    agent_runtime: AgentRuntime, base_state, stream_events
) -> None:
    events, writer = stream_events
    state = {**base_state, "assisted": True, "cards_shown": [SEND_LINK_CARD_ID]}
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    assert _refresh_send_link_card(_complete_draft(base_state), runtime, None) is None
    cards = _cards(events)
    assert [c["card_id"] for c in cards] == [SEND_LINK_CARD_ID]
    assert cards[0]["payload"]["can_send"] is True


def test_code_shows_the_card_when_a_write_completes_the_basic_info(
    agent_runtime: AgentRuntime, base_state, stream_events
) -> None:
    """F5 evals: no model call needed to show the card once the basic info is in."""
    events, writer = stream_events
    state = {**base_state, "assisted": True, "cards_shown": []}
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    shown = _refresh_send_link_card(_complete_draft(base_state), runtime, None)
    assert shown == [SEND_LINK_CARD_ID]
    assert [c["payload"]["can_send"] for c in _cards(events)] == [True]


def test_no_card_while_incomplete_outside_assisted_or_for_an_existing_contact(
    agent_runtime: AgentRuntime, base_state, stream_events
) -> None:
    events, writer = stream_events
    complete = _complete_draft(base_state)
    for state, draft in (
        ({**base_state, "assisted": True, "cards_shown": []}, new_inquiry_draft()),
        ({**base_state, "assisted": False, "cards_shown": [SEND_LINK_CARD_ID]}, complete),
        ({**base_state, "assisted": True, "cards_shown": [], "contact_check": "inform"}, complete),
    ):
        runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
        assert _refresh_send_link_card(draft, runtime, None) is None
    assert _cards(events) == []


def test_no_refresh_after_the_link_went_out(
    agent_runtime: AgentRuntime, base_state, stream_events
) -> None:
    events, writer = stream_events
    agent_runtime.services.audit.record(
        base_state["session_id"],
        "application_link_sent",
        actor="staff",
        payload={"by": "customer-care-1", "resend": False},
    )
    state = {**base_state, "assisted": True, "cards_shown": [SEND_LINK_CARD_ID]}
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    assert _refresh_send_link_card(_complete_draft(base_state), runtime, None) is None
    assert _cards(events) == []
