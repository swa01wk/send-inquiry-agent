"""Shared helpers for the review lifecycle tests (L4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from app.agent.case_graph import build_case_graph
from app.agent.graph import build_assisted_graph, build_graph
from app.agent.model import ScriptedChatModel
from app.agent.reviewer_graph import build_reviewer_graph
from app.config import Settings
from app.domain.draft_ops import write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.scenarios.helpers import chat_action, ready_to_submit_draft

STORE_CENTRAL = "rlm_store-central"
STORE_WESTERN = "rlm_store-western"
MEDIA_EASTERN = "rplm_media-eastern"
APPLICANT = "sara@beanstreet.example"


def lifecycle_settings(tmp_path: Path, **extra: Any) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        dev_tools=True,
        reviewer_console=True,
        callcentre_console=True,
        tenant_portal=True,
        agent_mode="scripted",
        token_secret="lifecycle-secret",
        **extra,
    )


@pytest.fixture
async def life(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, Any]]:
    settings = lifecycle_settings(tmp_path)

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}] * 50)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    application.state.assisted_graph = build_assisted_graph(model_factory=factory)
    application.state.case_graph = build_case_graph(model_factory=factory)
    application.state.reviewer_graph = build_reviewer_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, application


async def submit_case(
    client: AsyncClient, app: Any, *, unit_type: str = "store", mall: str = "riyadh-mall-a"
) -> str:
    """A submitted inquiry (through the real submit action); returns its reference."""
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    draft = ready_to_submit_draft(app)
    draft, _w, errors = write_fields(
        draft,
        [
            (FieldKey.UNIT_TYPE.value, unit_type, Source.USER),
            (FieldKey.MALLS.value, [mall], Source.USER),
        ],
        master=load_master_data(),
    )
    assert not errors
    session.draft = draft
    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    success = [d for n, d in events if n == "ui_card" and d["card_type"] == "success"]
    assert success, events
    return str(success[0]["payload"]["reference"])


async def act(
    client: AsyncClient, reviewer: str, reference: str, action: str, **payload: Any
) -> Any:
    return await client.post(
        f"/api/review/cases/{reference}/actions",
        json={"action": action, "payload": payload},
        headers={"X-Reviewer-Id": reviewer},
    )


def outbox(app: Any, to: str | None = None, template: str | None = None) -> list[dict[str, Any]]:
    messages = app.state.services.notifications.messages(to=to)
    return [m for m in messages if template is None or m["template"] == template]


def token_from(link: str) -> str:
    return parse_qs(urlparse(link).query)["t"][0]


pytestmark = pytest.mark.api
