"""Case-mode chat must use the case graph and never the intake router."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from app.agent.case_graph import build_case_graph
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from tests.lifecycle.conftest import APPLICANT, outbox, submit_case, token_from
from tests.scenarios.helpers import chat_message


async def test_case_session_chat_skips_router_and_uses_case_graph(life, monkeypatch) -> None:
    client, app = life

    reference = await submit_case(client, app)

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "Case assistant reply."}])

    intake_graph = build_graph(model_factory=factory)
    case_graph = build_case_graph(model_factory=factory)
    app.state.graph = intake_graph
    app.state.case_graph = case_graph

    route_calls: list[str] = []

    async def route_must_not_run(text: str, *_args: Any, **_kwargs: Any) -> None:
        route_calls.append(text)
        pytest.fail("route_message must not run for case-mode sessions")

    monkeypatch.setattr("app.api.chat.route_message", route_must_not_run)

    graphs_used: list[Any] = []
    real_run_turn = __import__("app.agent.events", fromlist=["run_turn"]).run_turn

    async def spy_run_turn(graph: Any, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        graphs_used.append(graph)
        async for item in real_run_turn(graph, *args, **kwargs):
            yield item

    monkeypatch.setattr("app.api.chat.run_turn", spy_run_turn)
    tracking = outbox(app, APPLICANT, "submission_email")[0]["links"][0]
    token = token_from(tracking)
    opened = await client.post("/api/cases/open", json={"token": token})
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["session_id"]

    events = await chat_message(client, session_id, "What is the status of my case?")
    assert route_calls == []
    assert graphs_used == [case_graph]
    assert graphs_used[0] is not intake_graph
    assert [name for name, _ in events if name == "token"]
    session = await app.state.session_store.get(session_id)
    assert (session.mode, session.case_id) == ("case", reference)
