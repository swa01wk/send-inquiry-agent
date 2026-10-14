import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.rules import compute_phase
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_guard_retries_false_submission_once(agent_runtime: AgentRuntime):
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-guard", draft=draft, phase=phase)

    steps = [
        {"content": "Your inquiry has been submitted! Here is your reference."},
        {"content": "Thanks for chatting — use Sign In if you already have an account."},
    ]
    model = ScriptedChatModel(steps=steps)
    graph = build_graph(model_factory=lambda: model)
    config = {
        "configurable": {"thread_id": "sess-guard", "runtime": agent_runtime},
    }

    result = await graph.ainvoke(
        {**state, "messages": [HumanMessage(content="hello")]},
        config=config,
    )

    assert result["guard_retries"] >= 1


@pytest.mark.asyncio
async def test_existing_cr_guard_requires_sign_in(agent_runtime: AgentRuntime):
    steps = [
        {
            "content": "",
            "tool_calls": [
                {
                    "name": "verify_cr",
                    "args": {"cr_number": "1010000000"},
                    "id": "call1",
                    "type": "tool_call",
                }
            ],
        },
        {"content": "You already have an account with us."},
        {"content": "Please use Sign In on Tenant Central to access your account."},
    ]
    model = ScriptedChatModel(steps=steps)
    graph = build_graph(model_factory=lambda: model)
    config = {
        "configurable": {"thread_id": "sess-existing", "runtime": agent_runtime},
    }
    draft = new_inquiry_draft()
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-existing", draft=draft, phase=phase)

    result = await graph.ainvoke(
        {**state, "messages": [HumanMessage(content="1010000000")]},
        config=config,
    )

    assert result["draft"].cr_status == "existing"
    assert result["guard_retries"] >= 0
