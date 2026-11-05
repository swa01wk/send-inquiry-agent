"""The public page's CR question through the API (demo feedback §3.1, D1–D2)."""

from __future__ import annotations

import json

import pytest
from app.agent.model import ScriptedChatModel
from app.domain.models import FieldKey
from app.policy.config import get_policy, use_policy
from httpx import AsyncClient
from tests.scenarios.helpers import chat_action, chat_message, ui_cards


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Signing in is the quickest way."}] * 5)


@pytest.fixture
def ask_first():
    with use_policy(get_policy().with_changes(public_cr_check="ask_then_sign_in")):
        yield


async def _session(client: AsyncClient) -> dict:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    return created.json()


async def test_welcome_asks_the_cr_question(client: AsyncClient, ask_first) -> None:
    created = await _session(client)
    card_types = [c["card_type"] for c in created["cards"]]
    assert card_types == ["cr_question"]
    assert "does your company have a CR" in created["messages"][-1]["text"]
    assert "number" not in json.dumps(created["cards"][0]["payload"]).lower()


async def test_welcome_unchanged_under_lookup(client: AsyncClient) -> None:
    created = await _session(client)
    assert [c["card_type"] for c in created["cards"]] == ["quick_replies"]


async def test_yes_shows_sign_in_and_stops(client: AsyncClient, app, ask_first) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "cr_answer", {"has_cr": True})
    question = ui_cards(events, "cr_question")
    sign_in = ui_cards(events, "sign_in_prompt")
    assert question and question[-1]["payload"]["answered"] == "yes"
    assert sign_in and sign_in[-1]["payload"]["sign_in_url"].endswith("/tenant")
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "existing"
    assert session.closed == "redirected_to_sign_in"
    audit = app.state.services.audit.events(session_id)
    assert any(
        e["type"] == "inquiry_redirected" and e["payload"]["reason"] == "has_cr" for e in audit
    )


async def test_no_carries_on_in_chat(client: AsyncClient, app, ask_first) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "cr_answer", {"has_cr": False})
    assert not ui_cards(events, "sign_in_prompt")
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "skipped"
    assert session.closed is None


async def test_answer_needs_a_boolean(client: AsyncClient, app, ask_first) -> None:
    session_id = (await _session(client))["session_id"]
    await chat_action(client, session_id, "cr_answer", {"has_cr": "yes"})
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "unknown"


async def test_typed_cr_number_is_never_kept(client: AsyncClient, app, ask_first) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_message(client, session_id, "Hi, my CR is 1010000000")
    assert ui_cards(events, "sign_in_prompt")
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "existing"
    assert session.draft.fields[FieldKey.CR_NUMBER].value is None
    stored = json.dumps(
        {
            "transcript": session.transcript,
            "draft": session.draft.model_dump(mode="json"),
            "audit": app.state.services.audit.events(session_id),
            "events": events,
        },
        ensure_ascii=False,
    )
    assert "1010000000" not in stored


async def test_cr_check_card_action_is_off(client: AsyncClient, app, ask_first) -> None:
    session_id = (await _session(client))["session_id"]
    await chat_action(client, session_id, "cr_check", {"cr_number": "1010123456"})
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "unknown"
    assert session.draft.fields[FieldKey.COMPANY_NAME].value is None
