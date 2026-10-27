import json
from datetime import UTC, datetime

import pytest
from app.agent.model import ScriptedChatModel
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.models import DocType
from httpx import AsyncClient
from tests.domain.conftest import fill_minimal_collectible


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Thanks — your review card is ready."}])


async def _read_sse(response) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    async for line in response.aiter_lines():
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current_event:
            events.append((current_event, json.loads(line.split(":", 1)[1].strip())))
    return events


async def _chat(client: AsyncClient, session_id: str, body: dict) -> list[tuple[str, dict]]:
    async with client.stream(
        "POST",
        f"/api/sessions/{session_id}/chat",
        json=body,
    ) as response:
        assert response.status_code == 200
        return await _read_sse(response)


@pytest.mark.asyncio
async def test_documents_complete_shows_review_card(client: AsyncClient, app) -> None:
    from app.domain.master import load_master_data

    store = app.state.session_store
    session = await store.create()
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.cr_status = "skipped"
    draft.email_verified = True
    draft.mobile_verified = True
    max_bytes = 5 * 1024 * 1024
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    draft, _ = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="1",
        file_name="co.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    draft, _ = add_document(
        draft,
        DocType.BRAND_PROFILE,
        file_id="2",
        file_name="brand.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    session.draft = draft

    events = await _chat(
        client,
        session.id,
        {"type": "action", "action": "documents_updated", "payload": {}},
    )
    cards = [data for name, data in events if name == "ui_card"]
    assert any(card["card_type"] == "review" for card in cards)


@pytest.mark.asyncio
async def test_documents_updated_premature_is_pending(client: AsyncClient, app) -> None:
    from app.domain.master import load_master_data

    store = app.state.session_store
    session = await store.create()
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.cr_status = "skipped"
    draft.email_verified = True
    draft.mobile_verified = True
    session.draft = draft

    from app.agent.actions import handle_ui_action
    from app.agent.runtime import AgentRuntime

    runtime = AgentRuntime(
        services=app.state.services,
        master=master,
        settings=app.state.settings,
    )
    result = await handle_ui_action("documents_updated", {}, session, runtime)
    assert "documents_pending" in result.note.content
