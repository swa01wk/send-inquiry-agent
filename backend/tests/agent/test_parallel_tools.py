from datetime import UTC, datetime

import pytest
from app.agent.events import run_turn
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey
from app.sessions import Session
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_parallel_tool_calls_merge_draft(agent_runtime, build_test_graph) -> None:
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
                    },
                    {
                        "name": "update_draft",
                        "args": {
                            "fields": [
                                {"key": "brand_name_en", "value": "Bean Street", "source": "user"},
                            ]
                        },
                        "id": "call_brand",
                        "type": "tool_call",
                    },
                ],
            },
            {"content": "Thanks — please confirm the details on the card."},
        ]
    )
    now = datetime.now(tz=UTC)
    session = Session(
        id="sess-parallel",
        draft=new_inquiry_draft(),
        created_at=now,
        last_seen=now,
    )

    events = [
        event
        async for event in run_turn(
            graph,
            session,
            HumanMessage(content="Marhaba\nMy CR number is 1010123456\nBean Street"),
            runtime=agent_runtime,
        )
    ]

    assert events[-1]["event"] == "done"
    assert session.draft.fields[FieldKey.CR_NUMBER].value == "1010123456"
    assert session.draft.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
