"""Case-mode sessions replay t2-reupload in AGENT_MODE=scripted (Day 4, story T2)."""

from __future__ import annotations

from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case, token_from
from tests.scenarios.helpers import chat_action, token_text, upload_document

T2_SCENARIO_HEADER = {"X-Test-Scenario": "t2-reupload"}


async def _open_reupload_case(client, app):
    reference = await submit_case(client, app)
    await act(
        client,
        STORE_CENTRAL,
        reference,
        "request_reupload",
        doc_types=["brand_profile"],
        remarks="Please send the current Brand Profile.",
    )
    mail = outbox(app, APPLICANT, "reupload_request")[0]
    token = token_from(mail["links"][0])
    return reference, token


async def test_case_open_without_scenario_header_has_no_script(life) -> None:
    client, app = life
    _reference, token = await _open_reupload_case(client, app)
    opened = await client.post("/api/cases/open", json={"token": token})
    assert opened.status_code == 200
    session = await app.state.session_store.get(opened.json()["session_id"])
    assert session.test_scenario is None


async def test_case_open_stores_e2e_script_from_header(life) -> None:
    client, app = life
    _reference, token = await _open_reupload_case(client, app)
    opened = await client.post(
        "/api/cases/open",
        json={"token": token},
        headers=T2_SCENARIO_HEADER,
    )
    assert opened.status_code == 200
    session = await app.state.session_store.get(opened.json()["session_id"])
    assert session.test_scenario == "t2-reupload"
    assert session.script_step == 0


async def test_case_chat_replays_t2_script_after_resubmit(life) -> None:
    client, app = life
    _reference, token = await _open_reupload_case(client, app)
    opened = await client.post(
        "/api/cases/open",
        json={"token": token},
        headers=T2_SCENARIO_HEADER,
    )
    session_id = opened.json()["session_id"]

    uploaded = await upload_document(
        client, session_id, "brand_profile", "brand_2026.pdf", b"%PDF-new"
    )
    assert uploaded["status_code"] == 200

    events = await chat_action(client, session_id, "resubmit_documents")
    tokens = token_text(events).lower()
    assert "thanks, your documents are back with the leasing team for first review." in tokens
    session = await app.state.session_store.get(session_id)
    assert session.script_step == 1
