from pathlib import Path

import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.rules import compute_phase
from app.services.container import build_services
from langgraph.prebuilt.tool_node import ToolRuntime


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
    )


@pytest.fixture
def agent_runtime(settings: Settings) -> AgentRuntime:
    services = build_services(settings)
    return AgentRuntime(services=services, master=load_master_data(), settings=settings)


@pytest.fixture
def base_state(agent_runtime: AgentRuntime):
    draft = new_inquiry_draft()
    phase = compute_phase(draft).value
    return initial_agent_state(session_id="test-session", draft=draft, phase=phase)


@pytest.fixture
def stream_events():
    events: list[dict] = []

    def writer(payload: dict) -> None:
        events.append(payload)

    return events, writer


def make_tool_runtime(
    *,
    state,
    agent_runtime: AgentRuntime,
    writer,
    tool_call_id: str = "call_test",
) -> ToolRuntime:
    return ToolRuntime(
        state=state,
        context=None,
        config={"configurable": {"thread_id": state["session_id"], "runtime": agent_runtime}},
        stream_writer=writer,
        tool_call_id=tool_call_id,
        store=None,
        tools=[],
    )


@pytest.fixture
def build_test_graph():
    def _build(steps: list[dict]):
        model = ScriptedChatModel(steps=steps)
        return build_graph(model_factory=lambda: model)

    return _build
