from unittest.mock import patch

from app.agent.guard import guard_node
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.agent.tools import confirm_fields
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.domain.rules import compute_phase
from langchain_core.messages import AIMessage, HumanMessage
from tests.agent.conftest import make_tool_runtime


def test_guard_derived_brand_en_not_confirmed_on_ok(agent_runtime: AgentRuntime) -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.BRAND_NAME_AR.value, "بين ستريت", Source.USER)],
        master=master,
    )
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-guard-brand", draft=draft, phase=phase)
    state["messages"] = [
        HumanMessage(content="Bean Street (بين ستريت) kiosk at Riyadh Mall A"),
        AIMessage(content="Got it — specialty kiosk at Riyadh Mall A."),
    ]
    state["guard_not_shown"] = []

    with patch("app.agent.guard.get_stream_writer", return_value=None):
        result = guard_node(state, runtime=agent_runtime)
    assert result["draft"].fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
    assert FieldKey.BRAND_NAME_EN.value in result["guard_not_shown"]

    state.update(result)
    state["messages"].append(HumanMessage(content="ok"))
    events: list[dict] = []

    def writer(payload: dict) -> None:
        events.append(payload)

    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    confirm_result = confirm_fields.invoke(
        {
            "keys": [FieldKey.BRAND_NAME_EN.value],
            "state": state,
            "runtime": runtime,
        },
    )
    assert confirm_result.update["draft"].fields[FieldKey.BRAND_NAME_EN].confirmed is False
    assert "No fields confirmed" in confirm_result.update["messages"][0].content
