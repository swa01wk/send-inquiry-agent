import json

import pytest
from app.agent.model import ScriptedChatModel
from app.api.cards import document_upload_payload
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from httpx import AsyncClient


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "OK"}])


async def _chat(client: AsyncClient, session_id: str, body: dict) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    async with client.stream(
        "POST",
        f"/api/sessions/{session_id}/chat",
        json=body,
    ) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current_event:
                events.append((current_event, json.loads(line.split(":", 1)[1].strip())))
    return events


def test_document_upload_payload_includes_cr_read_only() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.CR_NUMBER.value, "1010123456", Source.USER)],
        master=master,
    )
    payload = document_upload_payload(draft, master, max_mb=5)
    cr_row = next(row for row in payload.numbers if row.key == "cr_number")
    assert cr_row.value == "1010123456"
    assert cr_row.editable is False


@pytest.mark.asyncio
async def test_set_document_number_valid_vat(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    vat = "300000000000003"
    events = await _chat(
        client,
        session.id,
        {
            "type": "action",
            "action": "set_document_number",
            "payload": {"key": "vat_number", "value": vat},
        },
    )
    draft_events = [data for name, data in events if name == "draft"]
    assert draft_events
    assert session.draft.fields[FieldKey.VAT_NUMBER].value == vat
    assert session.draft.fields[FieldKey.VAT_NUMBER].source == Source.USER


@pytest.mark.asyncio
async def test_set_document_number_invalid_vat(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    await _chat(
        client,
        session.id,
        {
            "type": "action",
            "action": "set_document_number",
            "payload": {"key": "vat_number", "value": "100000000000001"},
        },
    )
    assert session.draft.fields[FieldKey.VAT_NUMBER].value is None
