"""Human handoff (L3 §3.6): the card, one call-centre case per inquiry, an audit event."""

from pathlib import Path

import pytest
from app.agent.graph import build_graph
from app.agent.handoff import inquiry_key, short_ref, transcript_summary
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.domain.conftest import fill_minimal_collectible
from tests.scenarios.helpers import chat_action, chat_message, ui_cards

CALL_CENTRE = "callcentre@test.example"


def _settings(tmp_path: Path, **extra) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        dev_tools=True,
        call_centre_email=CALL_CENTRE,
        call_centre_phone="+966 11 000 0000",
        call_centre_hours="Sun–Thu 9–5",
        **extra,
    )


@pytest.fixture
async def handoff_client(tmp_path: Path):
    settings = _settings(tmp_path)

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}] * 10)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, application


async def _session(client: AsyncClient, app, draft=None) -> str:
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    if draft is not None:
        session = await app.state.session_store.get(session_id)
        session.draft = draft
    return session_id


async def _notes(app, session_id: str) -> list[str]:
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    return [
        str(m.content)
        for m in snapshot.values.get("messages", [])
        if str(m.content).startswith("[ui_event]")
    ]


async def test_request_handoff_shows_card_and_opens_one_case(handoff_client) -> None:
    client, app = handoff_client
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    session_id = await _session(client, app, draft)
    await chat_message(client, session_id, "Can I talk to someone please?")

    events = await chat_action(client, session_id, "request_handoff", {"reason": "user_asked"})
    cards = ui_cards(events, "handoff")
    assert len(cards) == 1
    payload = cards[0]["payload"]
    assert payload["phone"] == "+966 11 000 0000"
    assert payload["email"] == CALL_CENTRE
    assert payload["hours"] == "Sun–Thu 9–5"
    assert payload["short_ref"].startswith("INQ-")
    assert payload["case_id"].startswith("CC-")
    assert payload["reason"] == "user_asked"
    assert "[ui_event] handoff_created user_asked" in await _notes(app, session_id)

    # The case is in the call centre's inbox (the dev inbox in the POC).
    inbox = (await client.get("/api/dev/outbox", params={"to": CALL_CENTRE})).json()["messages"]
    assert [m["template"] for m in inbox] == ["call_centre_case"]
    body = inbox[0]["body"]
    assert payload["case_id"] in body
    assert "Bean Street" in body
    assert "Can I talk to someone please?" in body

    # Asking again shows the same case; no second case is opened.
    again = await chat_action(client, session_id, "request_handoff", {})
    assert ui_cards(again, "handoff")[0]["payload"]["case_id"] == payload["case_id"]
    assert "[ui_event] handoff_created user_asked (repeat)" in await _notes(app, session_id)
    inbox = (await client.get("/api/dev/outbox", params={"to": CALL_CENTRE})).json()["messages"]
    assert len(inbox) == 1

    audit = (await client.get(f"/api/dev/audit/{session_id}")).json()["events"]
    handoffs = [e for e in audit if e["type"] == "handoff_created"]
    assert [h["payload"]["created"] for h in handoffs] == [True, False]
    assert all(h["payload"]["case_id"] == payload["case_id"] for h in handoffs)


async def test_handoff_keeps_the_inquiry_resumable(handoff_client) -> None:
    client, app = handoff_client
    session_id = await _session(client, app)
    await chat_action(client, session_id, "request_handoff", {"reason": "model_unavailable"})
    events = await chat_message(client, session_id, "Actually let's carry on here")
    assert any(name == "done" for name, _ in events)
    session = await app.state.session_store.get(session_id)
    assert "handoff" in session.cards


async def test_unknown_reason_falls_back_to_user_asked(handoff_client) -> None:
    client, app = handoff_client
    session_id = await _session(client, app)
    events = await chat_action(client, session_id, "request_handoff", {"reason": "<script>"})
    assert ui_cards(events, "handoff")[0]["payload"]["reason"] == "user_asked"


async def test_card_still_shows_when_the_case_system_is_down(tmp_path: Path) -> None:
    settings = _settings(tmp_path, mock_faults="call_centre:unavailable")

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}] * 5)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await _session(client, application)
        events = await chat_action(client, session_id, "request_handoff", {})
        payload = ui_cards(events, "handoff")[0]["payload"]
        assert payload["phone"] == "+966 11 000 0000"
        assert payload["case_id"] == ""
        notes = await _notes(application, session_id)
        expected = "[ui_event] handoff_created user_asked service_error call_centre unavailable"
        assert expected in notes


def test_summary_says_where_the_applicant_got_to() -> None:
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    summary = transcript_summary(draft, ["one", "two", "three", "four wants a person"])
    assert summary.startswith("Stage: verifying.")
    assert "Email must be verified" in summary
    assert '"one"' not in summary  # only the last three messages
    assert '"four wants a person"' in summary


def test_short_ref_and_inquiry_key() -> None:
    draft = new_inquiry_draft()
    assert short_ref(draft, "abcdef12-3456") == "INQ-ABCDEF"
    draft.reference = "GEO-SPC-123456"
    assert short_ref(draft, "abcdef12-3456") == "GEO-SPC-123456"
    assert inquiry_key("s1") == "s1"
    assert inquiry_key("s1", 2) == "s1~2"
