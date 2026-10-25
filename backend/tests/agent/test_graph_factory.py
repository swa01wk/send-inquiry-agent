import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.rules import compute_phase
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_model_factory_called_once_across_two_turns(agent_runtime: AgentRuntime):
    calls = 0

    def factory() -> ScriptedChatModel:
        nonlocal calls
        calls += 1
        return ScriptedChatModel(
            steps=[
                {"content": "Hello there."},
                {"content": "Anything else I can help with?"},
            ]
        )

    graph = build_graph(model_factory=factory)
    assert calls == 1

    draft = new_inquiry_draft()
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-factory", draft=draft, phase=phase)
    config = {"configurable": {"thread_id": "sess-factory", "runtime": agent_runtime}}

    await graph.ainvoke({**state, "messages": [HumanMessage(content="hi")]}, config=config)
    await graph.ainvoke({**state, "messages": [HumanMessage(content="thanks")]}, config=config)

    assert calls == 1
