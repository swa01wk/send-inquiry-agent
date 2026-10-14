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
from app.domain.models import FieldKey, Source
from app.domain.rules import compute_phase
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
