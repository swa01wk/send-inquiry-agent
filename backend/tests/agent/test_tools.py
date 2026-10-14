import pytest
from app.agent.state import initial_agent_state
from app.agent.tools import (
    confirm_fields,
    send_otp,
    show_review,
    skip_cr,
    update_draft,
    verify_cr,
)
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.models import FieldKey, FieldValue, Source
from app.domain.rules import compute_phase
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from tests.agent.conftest import make_tool_runtime


def _state_with_draft(draft, session_id: str = "sess-1"):
    phase = compute_phase(draft).value
    return initial_agent_state(session_id=session_id, draft=draft, phase=phase)


@pytest.mark.asyncio
async def test_verify_cr_existing_account(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = verify_cr.invoke(
        {"cr_number": "1010000000", "state": base_state, "runtime": runtime},
    )
    assert isinstance(result, Command)
    assert result.update["draft"].cr_status == "existing"


@pytest.mark.asyncio
async def test_verify_cr_new_emits_confirm_card(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = verify_cr.invoke(
        {"cr_number": "1010123456", "state": base_state, "runtime": runtime},
    )
    assert result.update["draft"].cr_status == "new"
    assert any(e.get("type") == "ui_card" for e in events)


@pytest.mark.asyncio
async def test_verify_cr_fawaz_does_not_fill_brand_en(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = verify_cr.invoke(
        {"cr_number": "1010222222", "state": base_state, "runtime": runtime},
    )
    draft = result.update["draft"]
    assert draft.fields[FieldKey.COMPANY_NAME].value == "Fawaz Alhokair Trading Co."
    assert draft.fields[FieldKey.BRAND_NAME_EN].value is None


def test_skip_cr_after_unknown(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = skip_cr.invoke({"state": base_state, "runtime": runtime})
    assert result.update["draft"].cr_status == "skipped"


def test_skip_cr_rejects_when_not_unknown(agent_runtime, base_state, stream_events):
    draft = base_state["draft"].model_copy(deep=True)
    draft.cr_status = "skipped"
    state = _state_with_draft(draft)
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = skip_cr.invoke({"state": state, "runtime": runtime})
    assert "already completed" in result.update["messages"][0].content


@pytest.mark.asyncio
async def test_send_otp_requires_email(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = await send_otp.ainvoke({"state": base_state, "runtime": runtime, "resend": False})
    assert "Need email" in result.update["messages"][0].content


def test_show_review_blocked(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = show_review.invoke({"state": base_state, "runtime": runtime})
    assert "Cannot show review" in result.update["messages"][0].content


def test_update_draft_rejects_terms(agent_runtime, base_state, stream_events):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = update_draft.invoke(
        {
            "fields": [{"key": "terms_accepted", "value": True, "source": "user"}],
            "state": base_state,
            "runtime": runtime,
        }
    )
    assert "protected" in result.update["messages"][0].content


def test_confirm_fields_already_confirmed(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.COMPANY_NAME.value, "Acme Co", Source.USER)],
        master=agent_runtime.master,
    )
    state = _state_with_draft(draft)
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.COMPANY_NAME.value], "state": state, "runtime": runtime},
    )
    assert "No fields confirmed" in result.update["messages"][0].content


def test_confirm_fields_skips_category_when_user_doubts(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe",
        source=Source.DERIVED,
        confirmed=False,
    )
    state = _state_with_draft(draft)
    state["messages"] = [HumanMessage(content="Hmm, not sure about the category")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": [FieldKey.SALES_CATEGORY.value], "state": state, "runtime": runtime},
    )
    assert "No fields confirmed" in result.update["messages"][0].content
    assert result.update["draft"].fields[FieldKey.SALES_CATEGORY].confirmed is False


@pytest.mark.asyncio
async def test_verify_cr_then_same_update_draft_keeps_verified(
    agent_runtime, base_state, stream_events
):
    events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    verified = verify_cr.invoke(
        {"cr_number": "1010123456", "state": base_state, "runtime": runtime},
    )
    draft = verified.update["draft"]
    cards_shown = verified.update["cards_shown"]
    confirm_card_keys = verified.update["confirm_card_keys"]
    state = _state_with_draft(draft)
    state["cards_shown"] = cards_shown
    state["confirm_card_keys"] = confirm_card_keys
    events.clear()
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    company = draft.fields[FieldKey.COMPANY_NAME].value
    result = update_draft.invoke(
        {
            "fields": [
                {"key": FieldKey.COMPANY_NAME.value, "value": company, "source": "derived"},
            ],
            "state": state,
            "runtime": runtime,
        },
    )
    assert result.update["draft"].fields[FieldKey.COMPANY_NAME].source == Source.VERIFIED
    assert "Unchanged: company_name" in result.update["messages"][0].content
    assert not any(e.get("type") == "ui_card" for e in events)


@pytest.mark.asyncio
async def test_confirm_fields_updates_existing_confirm_card(agent_runtime, stream_events):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.COMPANY_NAME.value, "Acme Co", Source.VERIFIED),
            (FieldKey.COMPANY_ADDRESS.value, "Main St", Source.VERIFIED),
        ],
        master=agent_runtime.master,
    )
    state = _state_with_draft(draft)
    state["cards_shown"] = ["confirm-1"]
    state["confirm_card_keys"] = {
        "confirm-1": [FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value],
    }
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {
            "keys": [FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value],
            "state": state,
            "runtime": runtime,
        },
    )
    assert "Confirmed:" in result.update["messages"][0].content
    card_events = [e for e in events if e.get("type") == "ui_card"]
    assert len(card_events) == 1
    card = card_events[0]["data"]
    assert card["card_id"] == "confirm-1"
    assert card["payload"]["all_confirmed"] is True
