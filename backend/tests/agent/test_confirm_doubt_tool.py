"""confirm_fields respects doubt in Arabic and English (L3 §3.10)."""

from app.agent.state import initial_agent_state
from app.agent.tools import confirm_fields
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, FieldValue, Source
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime


def _state(draft, text: str, **extra):
    state = initial_agent_state(session_id="s", draft=draft, phase="collecting", **extra)
    state["messages"] = [HumanMessage(content=text)]
    return state


def test_confirm_fields_skips_everything_on_general_doubt(agent_runtime, stream_events) -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.UNIT_TYPE] = FieldValue(value="kiosk", source=Source.DERIVED)
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(value="fnb_cafe", source=Source.DERIVED)
    state = _state(draft, "مو متأكد", turn_index=2)
    state["confirm_card_keys"] = {"confirm-1": ["unit_type", "sales_category"]}
    state["confirm_card_turns"] = {"confirm-1": 1}
    _events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": ["unit_type", "sales_category"], "state": state, "runtime": runtime}
    )
    content = result.update["messages"][0].content
    assert "No fields confirmed" in content
    assert "user_expressed_doubt" in content
    assert result.update["draft"].fields[FieldKey.UNIT_TYPE].confirmed is False


def test_confirm_fields_skips_only_the_doubted_field(agent_runtime, stream_events) -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.UNIT_TYPE] = FieldValue(value="kiosk", source=Source.DERIVED)
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(value="fnb_cafe", source=Source.DERIVED)
    state = _state(draft, "نوع الوحدة صحيح بس مو متأكد من الفئة", turn_index=2)
    state["confirm_card_keys"] = {"confirm-1": ["unit_type", "sales_category"]}
    state["confirm_card_turns"] = {"confirm-1": 1}
    _events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = confirm_fields.invoke(
        {"keys": ["unit_type", "sales_category"], "state": state, "runtime": runtime}
    )
    updated = result.update["draft"]
    assert updated.fields[FieldKey.UNIT_TYPE].confirmed is True
    assert updated.fields[FieldKey.SALES_CATEGORY].confirmed is False
