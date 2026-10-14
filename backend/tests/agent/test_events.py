from datetime import UTC, datetime

import pytest
from app.agent.events import run_turn
from app.domain.draft_ops import new_inquiry_draft
from app.sessions import Session
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_run_turn_event_order(agent_runtime, build_test_graph):
    graph = build_test_graph(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "name": "skip_cr",
                        "args": {},
                        "id": "call1",
                        "type": "tool_call",
                    }
                ],
            },
            {"content": "No problem — what is your company name?"},
        ]
    )
    now = datetime.now(tz=UTC)
    session = Session(
        id="sess-stream",
        draft=new_inquiry_draft(),
        created_at=now,
        last_seen=now,
    )

    events = [
        event
        async for event in run_turn(
            graph,
            session,
            HumanMessage(content="I don't have my CR handy"),
            runtime=agent_runtime,
        )
    ]

    types = [e["event"] for e in events]
    assert types[0] == "token"
    assert "draft" in types or "ui_card" in types
    assert types[-1] == "done"
    assert session.draft.cr_status == "skipped"
