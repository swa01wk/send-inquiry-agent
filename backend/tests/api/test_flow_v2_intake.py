"""Flow v2 public intake through the API: Check for Existing Customer (spec flow-v2-alignment
§3.2, day F3). The switch is off in the shipped policy; `intake_v2` turns it on."""

from __future__ import annotations

import json

import pytest
from app.agent.model import ScriptedChatModel
from app.domain.models import FieldKey
from httpx import AsyncClient
from tests.scenarios.helpers import chat_action, chat_message, token_text, ui_cards

pytestmark = pytest.mark.intake_v2

REGISTERED_CR = "1010000000"
NEW_CR = "1010123456"


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Thanks, let's carry on."}] * 6)


async def _session(client: AsyncClient) -> dict:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    return created.json()


def _flow_nodes(app, session_id: str) -> list[tuple[str, str | None]]:
    return [
        (e["payload"]["node"], e["payload"].get("outcome"))
        for e in app.state.services.audit.events(session_id)
        if e["type"] == "flow_step"
    ]


async def test_welcome_shows_the_company_registration_card(client: AsyncClient, app) -> None:
    created = await _session(client)
    cards = created["cards"]
    assert [c["card_type"] for c in cards] == ["company_registration", "quick_replies"]
    registration = cards[0]["payload"]
    assert registration["state"] == "open"
    assert registration["skip_confirm"]["prompt"] == (
        "Are you sure you want to proceed without CR ID?"
    )
    options = {o["label"]: o for o in cards[1]["payload"]["options"]}
    assert options["Continue my inquiry"]["action"] == "resume_pending"
    session = await app.state.session_store.get(created["session_id"])
    assert session.draft.intake_flow == "v2"
    assert ("start", None) in _flow_nodes(app, created["session_id"])


async def test_switch_off_keeps_the_v1_welcome(client: AsyncClient, app) -> None:
    from app.policy.config import get_policy, use_policy

    intake = get_policy().flow_v2_intake.model_dump(mode="json")
    with use_policy(get_policy().with_changes(flow_v2_intake={**intake, "enabled": False})):
        created = await _session(client)
    assert "company_registration" not in [c["card_type"] for c in created["cards"]]
    session = await app.state.session_store.get(created["session_id"])
    assert session.draft.intake_flow == "v1"


async def test_registered_cr_shows_sign_in_and_stops(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "cr_check", {"cr_number": REGISTERED_CR})
    registration = ui_cards(events, "company_registration")[-1]["payload"]
    assert registration["state"] == "registered"
    assert REGISTERED_CR not in json.dumps(registration)
    assert registration["cr_masked"].endswith(REGISTERED_CR[-4:])
    sign_in = ui_cards(events, "sign_in_prompt")
    assert sign_in and "already registered" in json.dumps(sign_in[-1]["payload"])
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "existing"
    assert session.closed == "redirected_to_sign_in"
    audit = app.state.services.audit.events(session_id)
    assert any(
        e["type"] == "inquiry_redirected" and e["payload"]["reason"] == "registered_cr"
        for e in audit
    )
    assert ("exist", "yes") in _flow_nodes(app, session_id)


async def test_new_cr_carries_on_and_keeps_the_number(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "cr_check", {"cr_number": NEW_CR})
    assert ui_cards(events, "company_registration")[-1]["payload"]["state"] == "not_registered"
    assert not ui_cards(events, "sign_in_prompt")
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "new"
    assert session.draft.fields[FieldKey.CR_NUMBER].value == NEW_CR
    # The registry's company name isn't written: Basic Info asks for it (M23).
    assert session.draft.fields[FieldKey.COMPANY_NAME].value is None
    assert session.closed is None
    assert ("exist", "no") in _flow_nodes(app, session_id)


async def test_invalid_cr_shows_the_error_on_the_card_quietly(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "cr_check", {"cr_number": "12"})
    registration = ui_cards(events, "company_registration")[-1]["payload"]
    assert registration["state"] == "open"
    assert registration["error"]
    assert token_text(events) == ""
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "unknown"


async def test_skip_asks_first_then_skips(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    first = await chat_action(client, session_id, "cr_skip", {})
    assert ui_cards(first, "company_registration")[-1]["payload"]["state"] == "confirm_skip"
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "unknown"
    confirmed = await chat_action(client, session_id, "cr_skip", {"confirmed": True})
    assert ui_cards(confirmed, "company_registration")[-1]["payload"]["state"] == "skipped"
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "skipped"
    assert ("exist", "skipped") in _flow_nodes(app, session_id)


async def test_cr_typed_in_chat_is_checked_and_never_kept_in_text(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_message(client, session_id, f"Hi, our CR is {NEW_CR}")
    assert ui_cards(events, "company_registration")[-1]["payload"]["state"] == "not_registered"
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "new"
    assert NEW_CR not in json.dumps(session.transcript)
    messages = [
        e for e in app.state.services.audit.events(session_id) if e["type"] == "user_message"
    ]
    assert NEW_CR not in json.dumps(messages)


async def test_accept_terms_sets_the_flag_and_updates_the_card(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    events = await chat_action(client, session_id, "accept_terms", {"terms_accepted": True})
    terms = ui_cards(events, "terms")
    assert terms and terms[-1]["payload"]["accepted"] is True
    assert terms[-1]["payload"]["privacy_url"].endswith("/privacy")
    session = await app.state.session_store.get(session_id)
    assert session.draft.terms_accepted is True
    audit = app.state.services.audit.events(session_id)
    assert any(e["type"] == "terms_accepted" for e in audit)


async def test_accept_terms_needs_the_checkbox(client: AsyncClient, app) -> None:
    session_id = (await _session(client))["session_id"]
    await chat_action(client, session_id, "accept_terms", {"terms_accepted": "yes"})
    session = await app.state.session_store.get(session_id)
    assert session.draft.terms_accepted is False
