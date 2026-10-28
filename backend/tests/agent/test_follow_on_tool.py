"""start_follow_on (L3 §3.11)."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.agent.state import initial_agent_state
from app.agent.tools import start_follow_on
from app.config import Settings
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime
from tests.scenarios.helpers import ready_to_submit_draft


@pytest.fixture
def fo_settings(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"))


def _submitted_draft(settings, verified_at):
    draft = ready_to_submit_draft(SimpleNamespace(state=SimpleNamespace(settings=settings)))
    draft.reference = "GEO-STR-111111"
    draft.terms_accepted = True
    draft.verified_at = verified_at
    return draft


def test_start_follow_on_needs_a_submitted_inquiry(agent_runtime, base_state, stream_events):
    _events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    result = start_follow_on.invoke({"state": base_state, "runtime": runtime})
    assert "No submitted inquiry yet" in result.update["messages"][0].content
    assert "inquiry_seq" not in result.update


def test_start_follow_on_refuses_the_same_mall(agent_runtime, fo_settings, stream_events):
    draft = _submitted_draft(fo_settings, datetime.now(tz=UTC))
    state = initial_agent_state(session_id="s", draft=draft, phase="submitted")
    state["messages"] = [HumanMessage(content="Riyadh Mall A again please")]
    _events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = start_follow_on.invoke(
        {"state": state, "runtime": runtime, "mall_id": "riyadh-mall-a"}
    )
    assert "already submitted" in result.update["messages"][0].content
    assert result.update["draft"].reference == "GEO-STR-111111"


def test_start_follow_on_without_a_named_mall(agent_runtime, fo_settings, stream_events):
    draft = _submitted_draft(fo_settings, datetime.now(tz=UTC))
    state = initial_agent_state(session_id="s", draft=draft, phase="submitted", turn_index=4)
    state["messages"] = [HumanMessage(content="Can we do another one?")]
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = start_follow_on.invoke({"state": state, "runtime": runtime})
    update = result.update
    assert update["inquiry_seq"] == 2
    assert update["cards_shown"] == ["confirm-1"]
    assert update["confirm_card_turns"] == {"confirm-1": 4}
    content = update["messages"][0].content
    assert content.startswith("follow_on_started from=GEO-STR-111111")
    assert "the mall, " in content
    cards = [e["data"] for e in events if e.get("type") == "ui_card"]
    assert cards[0]["payload"]["title"] == "Same details as GEO-STR-111111"
