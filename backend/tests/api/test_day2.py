"""Day 2: simulated Cenomi, link verification, resume, resend limits, submit once, tracking,
restart-safe sessions, audit log v0 and the gateway's fault handling (L3 §3.1–3.4)."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.domain.conftest import fill_minimal_collectible
from tests.scenarios.helpers import ready_to_submit_draft

EMAIL = "sara@beanstreet.example"
MOBILE = "+966501234567"


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


async def _post_chat(client: AsyncClient, session_id: str, body: dict) -> list[tuple[str, dict]]:
    async with client.stream("POST", f"/api/sessions/{session_id}/chat", json=body) as response:
        assert response.status_code == 200
        return await _read_sse(response)


async def _action(client, session_id, action, payload=None):
    body = {"type": "action", "action": action, "payload": payload or {}}
    return await _post_chat(client, session_id, body)


async def _notes(app, session_id: str) -> list[str]:
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    return [
        str(m.content)
        for m in snapshot.values.get("messages", [])
        if str(m.content).startswith("[ui_event]")
    ]


def _cards(events, card_type):
    return [d for name, d in events if name == "ui_card" and d["card_type"] == card_type]


async def _new_session(client: AsyncClient, app, draft=None):
    created = await client.post("/api/sessions")
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    if draft is not None:
        session.draft = draft
    return session


def _contact_draft():
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.cr_status = "skipped"
    return draft


# ---- Email link verification and resume (L3 §3.2) --------------------------------------


@pytest.mark.asyncio
async def test_link_verifies_once_and_resumes_the_chat(client, app) -> None:
    session = await _new_session(client, app, _contact_draft())
    await app.state.services.email_verification.send_link(session.id, EMAIL)

    outbox = (await client.get("/api/dev/outbox", params={"to": EMAIL})).json()["messages"]
    assert [m["template"] for m in outbox] == ["email_verification_link"]
    link = outbox[0]["links"][0]
    assert "/inquiry/verify?t=" in link
    token = parse_qs(urlparse(link).query)["t"][0]

    verified = await client.post("/api/verifications/email", json={"token": token})
    assert verified.status_code == 200
    body = verified.json()
    assert body["status"] == "verified"
    assert body["session_id"] == session.id
    assert session.draft.email_verified is True

    again = await client.post("/api/verifications/email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "token_used"

    resumed = await client.post("/api/sessions/resume", json={"token": body["resume_token"]})
    assert resumed.status_code == 200
    payload = resumed.json()
    assert payload["session_id"] == session.id
    assert payload["draft"]["checks"]["email_verified"] is True
    assert [m["id"] for m in payload["messages"]][:2] == ["welcome-1", "welcome-2"]


@pytest.mark.asyncio
async def test_link_for_a_changed_email_is_rejected(client, app) -> None:
    from app.domain.draft_ops import write_fields
    from app.domain.models import Source

    session = await _new_session(client, app, _contact_draft())
    await app.state.services.email_verification.send_link(session.id, EMAIL)
    token = app.state.services.email_verification.demo_token(session.id)
    session.draft, _, _ = write_fields(
        session.draft, [("email", "sara@other.example", Source.USER)], master=load_master_data()
    )
    response = await client.post("/api/verifications/email", json={"token": token})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_changed"
    assert session.draft.email_verified is False


@pytest.mark.asyncio
async def test_bad_tokens_are_refused(client) -> None:
    for endpoint in ("/api/verifications/email", "/api/sessions/resume"):
        response = await client.post(endpoint, json={"token": "not-a-token"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "token_invalid"


# ---- Resend limits (L3 §3.3) -----------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_is_throttled_with_a_countdown(client, app) -> None:
    session = await _new_session(client, app, _contact_draft())
    first = await _action(client, session.id, "resend_email_link")
    assert _cards(first, "verification")
    second = await _action(client, session.id, "resend_email_link")
    notes = await _notes(app, session.id)
    assert notes[-1].startswith("[ui_event] resend_throttled ")
    card = _cards(second, "verification")[-1]
    assert card["payload"]["email"]["resend_available_at"] is not None
    sent = app.state.services.notifications.messages(to=EMAIL)
    assert len(sent) == 1


# ---- Submit once, notifications, tracking (M0 §7.2, L3 §3.4) ----------------------------


async def _submit(client, session_id):
    return await _action(client, session_id, "accept_and_submit", {"terms_accepted": True})


@pytest.mark.asyncio
async def test_submit_once_notifies_and_tracks(client, app) -> None:
    session = await _new_session(client, app, ready_to_submit_draft(app))
    first = await _submit(client, session.id)
    success = _cards(first, "success")[0]["payload"]
    reference = success["reference"]
    assert f"/inquiry/status/{reference}?t=" in success["tracking_url"]

    second = await _submit(client, session.id)
    assert _cards(second, "success")[0]["payload"]["reference"] == reference
    notes = await _notes(app, session.id)
    assert notes[-1] == f"[ui_event] submitted reference={reference} (repeat)"
    assert len(app.state.services.submit.submissions) == 1

    outbox = app.state.services.notifications.messages()
    assert sorted(m["template"] for m in outbox) == ["submission_email", "submission_sms"]
    assert all(reference in m["body"] for m in outbox)

    token = parse_qs(urlparse(success["tracking_url"]).query)["t"][0]
    status = await client.get(f"/api/inquiries/{reference}", params={"t": token})
    assert status.status_code == 200
    body = status.json()
    assert [s["key"] for s in body["stages"]] == [
        "submitted",
        "first_review",
        "second_review",
        "outcome",
    ]
    assert [s["state"] for s in body["stages"]] == ["done", "current", "upcoming", "upcoming"]
    assert body["owner_role"] == "Regional Leasing Manager (Store)"
    assert body["waiting_on_you"] == []

    assert (await client.get(f"/api/inquiries/{reference}")).status_code == 404
    assert (await client.get(f"/api/inquiries/{reference}", params={"t": "x"})).status_code == 404
    other = await client.get("/api/inquiries/GEO-STR-000001", params={"t": token})
    assert other.status_code == 404


# ---- Faults end in a clear note and a resumable inquiry (L3 §3.1, E7) ------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "note"),
    [
        ("timeout", "submit_pending timeout"),
        ("unavailable", "submit_pending unavailable"),
        ("rejected", "submit_failed rejected"),
    ],
)
async def test_submit_faults_are_clear_and_recoverable(client, app, kind, note) -> None:
    session = await _new_session(client, app, ready_to_submit_draft(app))
    app.state.services.gateway.set_session_faults(session.id, f"submit:{kind}:1")
    failed = await _submit(client, session.id)
    assert not _cards(failed, "success")
    assert session.draft.reference is None
    assert (await _notes(app, session.id))[-1] == f"[ui_event] {note}"

    retried = await _submit(client, session.id)
    assert _cards(retried, "success")
    assert session.draft.reference


@pytest.mark.asyncio
async def test_invalid_kind_from_a_service(client, app, monkeypatch) -> None:
    session = await _new_session(client, app, ready_to_submit_draft(app))

    def bad_payload(*_args, **_kwargs):
        raise ValueError("payload rejected by schema")

    monkeypatch.setattr(app.state.services.submit, "submit", bad_payload)
    await _submit(client, session.id)
    assert (await _notes(app, session.id))[-1] == "[ui_event] submit_failed invalid"


@pytest.mark.asyncio
async def test_email_outage_is_a_clear_note(client, app) -> None:
    session = await _new_session(client, app, _contact_draft())
    app.state.services.gateway.set_session_faults(session.id, "email:unavailable:1")
    await _action(client, session.id, "resend_email_link")
    assert (await _notes(app, session.id))[-1] == "[ui_event] service_error email unavailable"
    assert app.state.services.notifications.messages() == []


@pytest.mark.asyncio
async def test_mock_faults_header_only_in_scripted_mode(tmp_path) -> None:
    for mode, expect_fault in (("scripted", True), ("openai", False)):
        settings = Settings(
            upload_dir=str(tmp_path / mode),
            agent_mode=mode,
            openai_api_key="sk-test",
            openai_model="test-model",
        )
        application = _app(settings)
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as http:
            created = await http.post("/api/sessions", headers={"X-Mock-Faults": "cr:timeout"})
        session_id = created.json()["session_id"]
        gateway = application.state.services.gateway
        assert (gateway._injected("cr", session_id) is not None) is expect_fault


@pytest.mark.asyncio
async def test_bad_mock_faults_header_is_a_400(tmp_path) -> None:
    application = _app(Settings(upload_dir=str(tmp_path / "u"), agent_mode="scripted"))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as http:
        created = await http.post("/api/sessions", headers={"X-Mock-Faults": "cr:explode"})
    assert created.status_code == 400
    assert created.json()["error"]["code"] == "bad_mock_faults"


# ---- Restart-safe sessions (L3 capability 7) --------------------------------------------


def _app(settings: Settings, steps=None):
    factory = lambda: ScriptedChatModel(steps=steps or [{"content": "OK"}])  # noqa: E731
    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(
        ttl_minutes=settings.session_ttl_minutes, data_dir=settings.data_dir
    )
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    return application


@pytest.mark.asyncio
async def test_backend_restart_mid_inquiry_continues(tmp_path) -> None:
    settings = Settings(upload_dir=str(tmp_path / "u"), data_dir=str(tmp_path / "data"))
    first_app = _app(settings, steps=[{"content": "Hi there."}, {"content": "Got it."}])
    async with AsyncClient(transport=ASGITransport(app=first_app), base_url="http://test") as http:
        session_id = (await http.post("/api/sessions")).json()["session_id"]
        await _post_chat(http, session_id, {"type": "message", "text": "Hello"})
        await _post_chat(http, session_id, {"type": "message", "text": "CR 1010123456"})
    before = await first_app.state.session_store.get(session_id)

    # A new process: new app, same DATA_DIR.
    second_app = _app(settings, steps=[{"content": "Carrying on."}])
    async with AsyncClient(transport=ASGITransport(app=second_app), base_url="http://test") as http:
        events = await _post_chat(http, session_id, {"type": "message", "text": "Next?"})
        draft = (await http.get(f"/api/sessions/{session_id}/draft")).json()
    assert any(name == "done" for name, _ in events)
    assert draft["phase"]
    after = await second_app.state.session_store.get(session_id)
    assert [m["text"] for m in after.transcript if m["role"] == "user"] == [
        "Hello",
        "CR 1010123456",
        "Next?",
    ]
    assert after.draft.model_dump(mode="json") == before.draft.model_dump(mode="json")
    assert after.turn_index == before.turn_index + 1
    # The model saw the earlier conversation again (restored from the transcript).
    snapshot = await second_app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    texts = [str(m.content) for m in snapshot.values["messages"]]
    assert "Hello" in texts and "Next?" in texts


# ---- Audit log v0 (L3 capability 10) ----------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_audit_trail_has_no_secrets(client, app) -> None:
    session = await _new_session(client, app, _contact_draft())
    await _post_chat(client, session.id, {"type": "message", "text": f"I'm Sara, {EMAIL}"})
    await _action(client, session.id, "resend_email_link")
    token = app.state.services.email_verification.demo_token(session.id)
    await _action(client, session.id, "verify_email", {"token": token})
    await _action(client, session.id, "resend_otp")
    await _action(client, session.id, "submit_otp", {"code": "1234"})
    session.draft = ready_to_submit_draft(app)
    await _submit(client, session.id)

    trail = (await client.get(f"/api/dev/audit/{session.id}")).json()["events"]
    types = {e["type"] for e in trail}
    assert {
        "inquiry_created",
        "user_message",
        "ui_action",
        "tool_called",
        "verification_sent",
        "verification_result",
        "submit_attempt",
        "submit_result",
        "notification_sent",
        "card_shown",
    } <= types
    dumped = json.dumps(trail)
    for secret in (token, EMAIL, MOBILE, "0501234567"):
        assert secret not in dumped
    # The OTP never appears as a value, and no payload carries a code or token key.
    assert '"1234"' not in dumped
    assert '"code"' not in dumped and '"token"' not in dumped


@pytest.mark.asyncio
async def test_dev_endpoints_need_dev_tools(tmp_path) -> None:
    application = _app(Settings(upload_dir=str(tmp_path / "u")))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as http:
        assert (await http.get("/api/dev/outbox")).status_code == 404
        assert (await http.get("/api/dev/audit/x")).status_code == 404


def test_dev_tools_refused_without_mock_integrations(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="DEV_TOOLS"):
        create_app(settings=Settings(dev_tools=True, integrations="live"))
    with pytest.raises(NotImplementedError):
        build_services(Settings(integrations="sandbox", upload_dir=str(tmp_path / "u")))
