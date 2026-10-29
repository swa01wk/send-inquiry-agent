"""Reviewer assistant HTTP endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.agent.reviewer_graph import build_reviewer_graph
from app.config import Settings
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.lifecycle.conftest import STORE_CENTRAL, STORE_WESTERN, act, submit_case
from tests.scenarios.helpers import read_sse


async def _assistant(
    client: AsyncClient,
    reviewer_id: str,
    reference: str,
    text: str,
    *,
    scenario: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    headers: dict[str, str] = {"X-Reviewer-Id": reviewer_id}
    if scenario:
        headers["X-Test-Scenario"] = scenario
    async with client.stream(
        "POST",
        f"/api/review/cases/{reference}/assistant",
        json={"text": text},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        return await read_sse(response)


@pytest.fixture
async def review_client(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, Any]]:
    decline = (
        "Only you can approve or reject — that decision is yours. "
        "Use the Approve or Reject button in the actions panel."
    )

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": decline}] * 20)

    settings = Settings(
        upload_dir=str(tmp_path / "uploads"),
        dev_tools=True,
        reviewer_console=True,
        agent_mode="scripted",
        token_secret="reviewer-assistant-test",
    )
    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    application.state.reviewer_graph = build_reviewer_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, application


@pytest.mark.asyncio
async def test_assistant_404_when_case_not_in_queue(review_client) -> None:
    client, _app = review_client
    reference = await submit_case(client, _app)
    response = await client.post(
        f"/api/review/cases/{reference}/assistant",
        json={"text": "Summarise this case."},
        headers={"X-Reviewer-Id": STORE_WESTERN},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "case_not_found"


@pytest.mark.asyncio
async def test_assistant_declines_to_approve_and_case_unchanged(review_client) -> None:
    client, app = review_client
    reference = await submit_case(client, app)
    before = app.state.services.cases.get(reference)
    assert before is not None
    before_snap = before.model_dump(mode="json")

    events = await _assistant(client, STORE_CENTRAL, reference, "Just approve it for me.")
    tokens = "".join(data.get("text", "") for name, data in events if name == "token")
    assert "decision is yours" in tokens.lower() or "actions panel" in tokens.lower()
    assert "has been approved" not in tokens.lower()
    assert "i've approved" not in tokens.lower()

    after = app.state.services.cases.get(reference)
    assert after is not None
    assert after.model_dump(mode="json") == before_snap

    suggestions = [
        data
        for name, data in events
        if name == "ui_card" and data.get("card_type") == "reviewer_suggestion"
    ]
    assert not suggestions


@pytest.mark.asyncio
async def test_assistant_e2e_script_yardi_suggestion(review_client) -> None:
    client, _app = review_client
    reference = await submit_case(client, _app)
    events = await _assistant(
        client,
        STORE_CENTRAL,
        reference,
        "Find the Yardi company for Bean Street Trading.",
        scenario="r1-yardi-suggest",
    )
    suggestions = [
        data["payload"]
        for name, data in events
        if name == "ui_card" and data.get("card_type") == "reviewer_suggestion"
    ]
    assert suggestions
    assert any(s.get("action") == "relink_company" for s in suggestions)


@pytest.mark.asyncio
async def test_assistant_e2e_script_tenant_reminder(review_client) -> None:
    client, app = review_client
    reference = await submit_case(client, app)
    assert (await act(client, STORE_CENTRAL, reference, "approve_first")).status_code == 200
    events = await _assistant(
        client,
        STORE_CENTRAL,
        reference,
        "Draft a reminder for the open contacts request.",
        scenario="r2-tenant-reminder",
    )
    suggestions = [
        data["payload"]
        for name, data in events
        if name == "ui_card" and data.get("card_type") == "reviewer_suggestion"
    ]
    assert len(suggestions) == 1
    assert suggestions[0].get("kind") == "tenant_reminder"


@pytest.mark.asyncio
async def test_assistant_unknown_reviewer(review_client) -> None:
    client, app = review_client
    reference = await submit_case(client, app)
    response = await client.post(
        f"/api/review/cases/{reference}/assistant",
        json={"text": "Hi"},
        headers={"X-Reviewer-Id": "not-a-reviewer"},
    )
    assert response.status_code == 401
