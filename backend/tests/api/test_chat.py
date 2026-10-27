import json
import re
from datetime import UTC, datetime

import pytest
from app.agent.model import ScriptedChatModel
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.models import DocType, FieldKey, Source
from app.services.otp import MockOtpService
from httpx import AsyncClient
from tests.domain.conftest import fill_minimal_collectible


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
        assert "text/event-stream" in response.headers.get("content-type", "")
        return await _read_sse(response)


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Hello from the assistant!"}])


@pytest.mark.asyncio
async def test_chat_message_streams_token_and_done(client: AsyncClient) -> None:
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    events = await _chat(
        client,
        session_id,
        {"type": "message", "text": "Hi there"},
    )
    types = [name for name, _ in events]
    assert "token" in types
    assert types[-1] == "done"
    token_data = next(data for name, data in events if name == "token")
    assert "message_id" in token_data
    assert token_data["text"]


@pytest.mark.asyncio
async def test_select_malls_emits_draft_before_agent(client: AsyncClient) -> None:
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    events = await _chat(
        client,
        session_id,
        {
            "type": "action",
            "action": "select_malls",
            "payload": {"mall_ids": ["riyadh-mall-a"]},
        },
    )
    draft_events = [data for name, data in events if name == "draft"]
    assert draft_events
    assert draft_events[0]["changed_keys"] == ["malls"]
    assert draft_events[0]["fields"]  # sanity


@pytest.mark.asyncio
async def test_submit_otp_wrong_codes_resend_and_no_code_in_history(
    client: AsyncClient,
    app,
) -> None:
    store = app.state.session_store
    session = await store.create()
    from app.domain.master import load_master_data

    master_data = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master_data)
    draft.cr_status = "skipped"
    session.draft = draft
    draft.otp_sent_to = "+966501234567"
    otp: MockOtpService = app.state.services.otp
    await otp.send(session.id, "+966501234567")

    secret = "9999"
    for _ in range(3):
        events = await _chat(
            client,
            session.id,
            {"type": "action", "action": "submit_otp", "payload": {"code": secret}},
        )
        assert any(name == "draft" for name, _ in events)

    assert session.draft.otp_attempts_left == 3
    snapshot = await app.state.graph.aget_state(
        {"configurable": {"thread_id": session.id}},
    )
    messages_blob = json.dumps(snapshot.values.get("messages", []), default=str)
    assert secret not in messages_blob


@pytest.mark.asyncio
async def test_accept_and_submit_blocked_shows_review(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    from app.domain.master import load_master_data

    session.draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    session.draft.cr_status = "skipped"

    events = await _chat(
        client,
        session.id,
        {"type": "action", "action": "accept_and_submit", "payload": {"terms_accepted": True}},
    )
    cards = [data for name, data in events if name == "ui_card"]
    assert any(card["card_type"] == "review" for card in cards)
    review = next(card for card in cards if card["card_type"] == "review")
    assert review["payload"]["blockers"]


@pytest.mark.asyncio
async def test_accept_and_submit_success_reference(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    from app.domain.master import load_master_data

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
        {"type": "action", "action": "accept_and_submit", "payload": {"terms_accepted": True}},
    )
    success = next(
        data for name, data in events if name == "ui_card" and data.get("card_type") == "success"
    )
    reference = success["payload"]["reference"]
    assert re.match(r"^GEO-(STR|MED|SPC)-\d{6}$", reference)
    assert session.draft.reference == reference


@pytest.mark.asyncio
async def test_concurrent_chat_returns_409(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    await store.begin_turn(session.id)
    try:
        response = await client.post(
            f"/api/sessions/{session.id}/chat",
            json={"type": "message", "text": "hello"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "turn_in_progress"
    finally:
        await store.end_turn(session.id)


@pytest.mark.asyncio
async def test_verify_email_action_with_link_token(client: AsyncClient, app) -> None:
    from app.domain.master import load_master_data

    store = app.state.session_store
    session = await store.create()
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.cr_status = "skipped"
    draft.email_link_sent_to = "sara@beanstreet.example"
    session.draft = draft
    links = app.state.services.email_verification
    await links.send_link(session.id, "sara@beanstreet.example")

    events = await _chat(
        client,
        session.id,
        {"type": "action", "action": "verify_email", "payload": {"token": "not-the-token"}},
    )
    assert session.draft.email_verified is False
    assert any(name == "ui_card" and data["card_type"] == "verification" for name, data in events)

    token = links.demo_token(session.id)
    await _chat(
        client,
        session.id,
        {"type": "action", "action": "verify_email", "payload": {"token": token}},
    )
    assert session.draft.email_verified is True
    # The mobile still needs its code, so the phase stays at verification.
    assert session.draft.mobile_verified is False


@pytest.mark.asyncio
async def test_verify_email_rejected_after_email_changed(client: AsyncClient, app) -> None:
    from app.domain.draft_ops import write_fields
    from app.domain.master import load_master_data

    master = load_master_data()
    store = app.state.session_store
    session = await store.create()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.cr_status = "skipped"
    links = app.state.services.email_verification
    await links.send_link(session.id, "sara@beanstreet.example")
    draft, _, _ = write_fields(draft, [("email", "sara@other.example", Source.USER)], master=master)
    session.draft = draft

    await _chat(
        client,
        session.id,
        {
            "type": "action",
            "action": "verify_email",
            "payload": {"token": links.demo_token(session.id)},
        },
    )
    assert session.draft.email_verified is False


@pytest.mark.asyncio
async def test_select_two_malls_rejected(client: AsyncClient, app) -> None:
    store = app.state.session_store
    session = await store.create()
    await _chat(
        client,
        session.id,
        {
            "type": "action",
            "action": "select_malls",
            "payload": {"mall_ids": ["riyadh-mall-a", "riyadh-mall-b"]},
        },
    )
    assert session.draft.fields[FieldKey.MALLS].value is None
