"""Card actions whose outcome the card already shows run no agent turn (spec §6), and
documents can come before verification without the agent pointing to Submit early.

Nov 2026 manual test: every wrong code, resend and single-channel tick produced its own
agent reply, and documents uploaded before the email link led to "everything's in"."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey
from httpx import AsyncClient
from tests.domain.conftest import fill_minimal_collectible


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        session_ttl_minutes=120,
        dev_tools=True,
        token_secret="test-secret",
    )


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "OK"}])


async def _read_sse(response) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current: str | None = None
    async for line in response.aiter_lines():
        if not line:
            continue
        if line.startswith("event:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current:
            events.append((current, json.loads(line.split(":", 1)[1].strip())))
    return events


async def _action(client: AsyncClient, session_id: str, action: str, payload=None):
    body = {"type": "action", "action": action, "payload": payload or {}}
    async with client.stream("POST", f"/api/sessions/{session_id}/chat", json=body) as response:
        assert response.status_code == 200
        return await _read_sse(response)


async def _notes(app, session_id: str) -> list[str]:
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    return [
        str(m.content)
        for m in (snapshot.values or {}).get("messages", [])
        if str(m.content).startswith("[ui_event]")
    ]


def _names(events) -> list[str]:
    return [name for name, _ in events]


async def _session_with_contact(client: AsyncClient, app):
    created = await client.post("/api/sessions")
    session = await app.state.session_store.get(created.json()["session_id"])
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.cr_status = "skipped"
    session.draft = draft
    return session


def _upload_required(draft):
    for doc_type, file_id in ((DocType.COMPANY_PROFILE, "co-1"), (DocType.BRAND_PROFILE, "br-1")):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=f"{file_id}.pdf",
            size_bytes=100,
            max_bytes=5 * 1024 * 1024,
            uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    return draft


@pytest.mark.asyncio
async def test_resend_and_wrong_code_update_the_card_without_a_reply(client, app) -> None:
    session = await _session_with_contact(client, app)

    resent = await _action(client, session.id, "resend_otp")
    wrong = await _action(client, session.id, "submit_otp", {"code": "0000"})

    for events in (resent, wrong):
        assert "token" not in _names(events)
        assert _names(events)[-1] == "done"
        assert "ui_card" in _names(events)
    card = [d for n, d in wrong if n == "ui_card" and d["card_type"] == "verification"][-1]
    assert card["payload"]["mobile"]["attempts_left"] == 2
    assert await _notes(app, session.id) == []


@pytest.mark.asyncio
async def test_one_channel_verified_is_quiet_both_verified_gets_a_reply(client, app) -> None:
    session = await _session_with_contact(client, app)
    email = str(session.draft.fields[FieldKey.EMAIL].value)
    services = app.state.services
    await services.email_verification.send_link(session.id, email)
    session.draft.email_link_sent_to = email
    await _action(client, session.id, "resend_otp")

    mobile_done = await _action(client, session.id, "submit_otp", {"code": "1234"})
    assert "token" not in _names(mobile_done)
    draft_events = [d for n, d in mobile_done if n == "draft"]
    assert draft_events[-1]["checks"]["next_step"] == "verify_email"

    token = services.email_verification.demo_token(session.id)
    both_done = await _action(client, session.id, "verify_email", {"token": token})
    assert "token" in _names(both_done)
    notes = await _notes(app, session.id)
    assert notes == ["[ui_event] email_verified verification_complete"]


@pytest.mark.asyncio
async def test_verification_after_the_documents_says_they_are_in(client, app) -> None:
    """Re-demo flow 1 (10 Nov): on the upload path the profiles come before verification,
    so verification_complete must say so, or the agent shows and lists them again."""
    session = await _session_with_contact(client, app)
    session.draft = _upload_required(session.draft)
    session.draft.mobile_verified = True
    email = str(session.draft.fields[FieldKey.EMAIL].value)
    services = app.state.services
    await services.email_verification.send_link(session.id, email)
    session.draft.email_link_sent_to = email

    token = services.email_verification.demo_token(session.id)
    await _action(client, session.id, "verify_email", {"token": token})
    notes = await _notes(app, session.id)
    assert notes == ["[ui_event] email_verified verification_complete documents_complete"]


@pytest.mark.asyncio
async def test_documents_before_the_email_link_say_what_is_still_needed(client, app) -> None:
    session = await _session_with_contact(client, app)
    draft = _upload_required(session.draft)
    draft.mobile_verified = True
    session.draft = draft

    await _action(client, session.id, "documents_updated")

    notes = await _notes(app, session.id)
    assert notes[-1] == "[ui_event] documents_complete still_needed=verify_email"


@pytest.mark.asyncio
async def test_documents_complete_names_a_missing_field(client, app) -> None:
    # Re-demo flow 3 (10 Nov): `still_needed=fields` led the agent to the verification card;
    # the Arabic brand name was what was missing.
    from app.domain.models import FieldValue

    session = await _session_with_contact(client, app)
    session.draft = _upload_required(session.draft)
    session.draft.email_verified = True
    session.draft.mobile_verified = True
    session.draft.fields[FieldKey.BRAND_NAME_AR] = FieldValue()

    await _action(client, session.id, "documents_updated")

    notes = await _notes(app, session.id)
    assert notes[-1] == "[ui_event] documents_complete still_needed=brand_name_ar"


@pytest.mark.asyncio
async def test_an_edit_resends_the_review_card_once_it_is_shown(client, app) -> None:
    # Re-demo flow 3 (10 Nov): rent and lease edits left the review card showing
    # "Not yet collected".
    session = await _session_with_contact(client, app)
    session.remember_card({"card_id": "review", "card_type": "review", "message_id": "m7"})

    events = await _action(client, session.id, "edit_field", {"key": "lease_period", "value": "3y"})

    reviews = [d for n, d in events if n == "ui_card" and d["card_type"] == "review"]
    assert len(reviews) == 1
    assert reviews[0]["message_id"] == "m7"
    lease = [
        row for g in reviews[0]["payload"]["groups"] for row in g["rows"] if row["key"] == "lease"
    ]
    assert lease and lease[0]["display"]


@pytest.mark.asyncio
async def test_an_edit_sends_no_review_card_before_it_is_shown(client, app) -> None:
    session = await _session_with_contact(client, app)
    events = await _action(client, session.id, "edit_field", {"key": "first_name", "value": "Sara"})
    assert not [d for n, d in events if n == "ui_card" and d["card_type"] == "review"]
