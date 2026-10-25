import pytest
from app.agent.graph import build_graph
from app.agent.guard import GUARD_PREFIX
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.domain.rules import compute_phase
from langchain_core.messages import HumanMessage
from tests.scenarios.agent_steps import tool_step


@pytest.mark.asyncio
async def test_guard_retries_when_contact_omitted(agent_runtime: AgentRuntime) -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.COMPANY_NAME.value, "Acme Trading LLC", Source.USER),
            (FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER),
            (FieldKey.MALLS.value, ["riyadh-mall-a"], Source.USER),
        ],
        master=master,
    )
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-contact-guard", draft=draft, phase=phase)

    user_text = "Abdullah Al Harbi, abdullah@beanstreet.example, 0551234567"
    steps = [
        {"content": "Thanks — I have your details."},
        tool_step(
            "update_draft",
            {
                "fields": [
                    {"key": "first_name", "value": "Abdullah", "source": "user"},
                    {"key": "last_name", "value": "Al Harbi", "source": "user"},
                    {"key": "email", "value": "abdullah@beanstreet.example", "source": "user"},
                    {"key": "contact_number", "value": "0551234567", "source": "user"},
                ]
            },
            "s2",
        ),
        tool_step("send_verification", {"resend": False}, "s3"),
        {"content": "Enter the verification code when it arrives."},
    ]
    model = ScriptedChatModel(steps=steps)
    graph = build_graph(model_factory=lambda: model)
    config = {
        "configurable": {"thread_id": "sess-contact-guard", "runtime": agent_runtime},
    }

    result = await graph.ainvoke(
        {**state, "messages": [HumanMessage(content=user_text)]},
        config=config,
    )

    assert result["guard_retries"] >= 1
    assert result["draft"].fields[FieldKey.FIRST_NAME].value == "Abdullah"
    assert result["draft"].fields[FieldKey.LAST_NAME].value == "Al Harbi"
    guard_notes = [
        str(message.content)
        for message in result["messages"]
        if isinstance(message.content, str) and message.content.startswith(GUARD_PREFIX)
    ]
    assert any("update_draft" in note and "Al Harbi" in note for note in guard_notes)
