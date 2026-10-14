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
    assert "token" in types
    # Draft updates stream live (before the reply finishes); done is always last.
    assert "draft" in types
    assert types.index("draft") < types.index("done")
    assert types[-1] == "done"
    assert session.draft.cr_status == "skipped"


@pytest.mark.asyncio
async def test_cards_attach_to_final_reply(agent_runtime, build_test_graph):
    graph = build_test_graph(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "name": "verify_cr",
                        "args": {"cr_number": "1010123456"},
                        "id": "call_cr",
                        "type": "tool_call",
                    }
                ],
            },
            {"content": "Found you. Here's what your CR says; tell me if anything's off."},
        ]
    )
    now = datetime.now(tz=UTC)
    session = Session(id="sess-cards", draft=new_inquiry_draft(), created_at=now, last_seen=now)

    events = [
        event
        async for event in run_turn(
            graph,
            session,
            HumanMessage(content="My CR is 1010123456"),
            runtime=agent_runtime,
        )
    ]

    types = [e["event"] for e in events]
    token_ids = {e["data"]["message_id"] for e in events if e["event"] == "token"}
    cards = [e for e in events if e["event"] == "ui_card"]
    assert len(token_ids) == 1
    assert cards
    assert all(card["data"]["message_id"] in token_ids for card in cards)
    # Cards are flushed after the reply text, just before done.
    assert max(i for i, t in enumerate(types) if t == "token") < types.index("ui_card")


@pytest.mark.asyncio
async def test_guard_retraction_removes_rejected_reply(agent_runtime, build_test_graph):
    graph = build_test_graph(
        [
            {"content": "Your inquiry has been submitted!"},
            {"content": "Happy to help. Do you have your CR number handy?"},
        ]
    )
    now = datetime.now(tz=UTC)
    session = Session(id="sess-retract", draft=new_inquiry_draft(), created_at=now, last_seen=now)

    events = [
        event
        async for event in run_turn(
            graph,
            session,
            HumanMessage(content="hello"),
            runtime=agent_runtime,
        )
    ]

    tokens = [e for e in events if e["event"] == "token"]
    removed = [e["data"]["message_id"] for e in events if e["event"] == "message_remove"]
    shown_ids = [t["data"]["message_id"] for t in tokens]
    # Whatever streamed for the rejected reply is removed; the retry is a new bubble.
    final_id = shown_ids[-1]
    assert final_id not in removed
    final_text = "".join(t["data"]["text"] for t in tokens if t["data"]["message_id"] == final_id)
    assert "CR number" in final_text
    for message_id in removed:
        assert message_id != final_id
