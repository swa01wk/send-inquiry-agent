"""Confirm-fields 'shown before turn' policy (pre-baseline F1)."""

from app.agent.tools import confirm_fields, update_draft
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.models import FieldKey, FieldValue, Source
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime


def _state_with_draft(draft, *, turn_index: int = 1, confirm_card_turns: dict | None = None):
    from app.agent.state import initial_agent_state
    from app.domain.rules import compute_phase

    state = initial_agent_state(
        session_id="test-session",
        draft=draft,
        phase=compute_phase(draft).value,
        turn_index=turn_index,
        confirm_card_turns=confirm_card_turns or {},
    )
    state["confirm_card_keys"] = {"confirm-1": [FieldKey.UNIT_TYPE.value]}
    if confirm_card_turns is None:
        state["confirm_card_turns"] = {"confirm-1": turn_index}
    state["cards_shown"] = ["confirm-1"]
    return state


def test_derived_same_turn_skipped_not_shown(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft.fields[FieldKey.UNIT_TYPE] = FieldValue(
        value="store",
        source=Source.DERIVED,
        confirmed=False,
    )
    state = _state_with_draft(draft, turn_index=2, confirm_card_turns={"confirm-1": 2})
    state["messages"] = [HumanMessage(content="Thanks, sounds good")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.UNIT_TYPE.value], "state": state, "runtime": runtime},
    )
    assert "not_shown" in result.update["messages"][0].content
    assert not result.update["draft"].fields[FieldKey.UNIT_TYPE].confirmed


def test_derived_next_turn_confirmed(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft.fields[FieldKey.UNIT_TYPE] = FieldValue(
        value="store",
        source=Source.DERIVED,
        confirmed=False,
    )
    state = _state_with_draft(draft, turn_index=2, confirm_card_turns={"confirm-1": 1})
    state["messages"] = [HumanMessage(content="Yes that's correct")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.UNIT_TYPE.value], "state": state, "runtime": runtime},
    )
    assert "Confirmed:" in result.update["messages"][0].content
    assert result.update["draft"].fields[FieldKey.UNIT_TYPE].confirmed is True


def test_key_never_on_confirm_card_skipped(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe",
        source=Source.DERIVED,
        confirmed=False,
    )
    state = _state_with_draft(draft, turn_index=2, confirm_card_turns={"confirm-1": 1})
    state["confirm_card_keys"] = {"confirm-1": [FieldKey.UNIT_TYPE.value]}
    state["messages"] = [HumanMessage(content="ok")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.SALES_CATEGORY.value], "state": state, "runtime": runtime},
    )
    assert "not_shown" in result.update["messages"][0].content


def test_verify_cr_prefill_follows_shown_rule(agent_runtime, stream_events, base_state):
    base_state["turn_index"] = 1
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    from app.agent.tools import verify_cr

    verified = verify_cr.invoke(
        {"cr_number": "1010123456", "state": base_state, "runtime": runtime},
    )
    draft = verified.update["draft"]
    state = _state_with_draft(
        draft,
        turn_index=1,
        confirm_card_turns=verified.update.get("confirm_card_turns", {}),
    )
    state["confirm_card_keys"] = verified.update["confirm_card_keys"]
    state["messages"] = [HumanMessage(content="1010123456")]
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {
            "keys": [FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value],
            "state": state,
            "runtime": runtime,
        },
    )
    assert "not_shown" in result.update["messages"][0].content


def test_reemitted_card_waits_a_turn(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER),
            (FieldKey.UNIT_TYPE.value, "specialty", Source.DERIVED),
        ],
        master=agent_runtime.master,
    )
    state = _state_with_draft(draft, turn_index=2, confirm_card_turns={"confirm-1": 1})
    state["messages"] = [HumanMessage(content="Actually it's a store")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    updated = update_draft.invoke(
        {
            "fields": [{"key": FieldKey.UNIT_TYPE.value, "value": "store", "source": "user"}],
            "state": state,
            "runtime": runtime,
        },
    )
    turns = updated.update.get("confirm_card_turns", {})
    assert turns.get("confirm-1") == 2
    state2 = _state_with_draft(
        updated.update["draft"],
        turn_index=2,
        confirm_card_turns=turns,
    )
    state2["confirm_card_keys"] = updated.update["confirm_card_keys"]
    state2["messages"] = [HumanMessage(content="yes")]
    runtime = make_tool_runtime(state=state2, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.UNIT_TYPE.value], "state": state2, "runtime": runtime},
    )
    assert "not_shown" in result.update["messages"][0].content
