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


async def test_reopening_with_another_script_starts_it(life) -> None:
    """Day R5: the rehearsal opens the same case chat for the re-upload (t2-reupload), then
    for the contacts (rd-contact-approval); the second link starts the second script."""
    client, app = life
    _reference, token = await _open_reupload_case(client, app)
    first = await client.post("/api/cases/open", json={"token": token}, headers=T2_SCENARIO_HEADER)
    session_id = first.json()["session_id"]
    store = app.state.session_store
    session = await store.get(session_id)
    session.script_step = 3
    await store.save(session)

    same = await client.post("/api/cases/open", json={"token": token}, headers=T2_SCENARIO_HEADER)
    assert same.json()["session_id"] == session_id
    assert (await store.get(session_id)).script_step == 3  # same script: carries on

    other = await client.post(
        "/api/cases/open", json={"token": token}, headers={"X-Test-Scenario": "rd-contact-approval"}
    )
    assert other.json()["session_id"] == session_id
    session = await store.get(session_id)
    assert (session.test_scenario, session.script_step) == ("rd-contact-approval", 0)
