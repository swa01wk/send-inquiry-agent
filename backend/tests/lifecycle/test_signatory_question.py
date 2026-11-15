"""The signatory question on a contacts request (demo feedback §3.5, D8). Runs with the
shipped policy. Per-contact approval was removed with flow v2 (V7, M15)."""

from __future__ import annotations

from typing import Any

import pytest
from app.workflow.contacts import write_contacts
from app.workflow.models import TenantContact
from tests.lifecycle.conftest import APPLICANT, act, outbox, submit_case, token_from
from tests.lifecycle.test_document_approval import (
    LEASE_ADMIN,
    approve_documents,
    reviewed,
)
from tests.scenarios.helpers import chat_action, ui_cards

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]

LEASE_ADMIN_EMAIL = "reem.almutairi@cenomi.example"
OMAR = {
    "role": "billing_contact",
    "first_name": "Omar",
    "last_name": "Saleh",
    "email": "omar@beanstreet.example",
    "contact_number": "+966551234567",
}


async def _second_review(client, app) -> str:
    reference = await submit_case(client, app, prepare=reviewed())
    await approve_documents(client, reference)
    assert (await act(client, LEASE_ADMIN, reference, "approve_first")).status_code == 200
    return reference


async def _open(client, link: str) -> dict[str, Any]:
    response = await client.post("/api/cases/open", json={"token": token_from(link)})
    assert response.status_code == 200, response.text
    return response.json()


def _card(opened: dict[str, Any], card_type: str) -> list[dict[str, Any]]:
    return [c for c in opened["cards"] if c["card_type"] == card_type]


async def _send(client, app, session_id: str, entries: list[dict[str, Any]]) -> None:
    session = await app.state.session_store.get(session_id)
    current = [TenantContact.model_validate(c) for c in session.contacts_draft]
    contacts, errors = write_contacts(current, entries, session.draft)
    assert errors == {}
    session.contacts_draft = [c.model_dump(mode="json") for c in contacts]
    sent = await chat_action(client, session_id, "submit_contacts")
    assert ui_cards(sent, "case_status"), sent


def _contact(data: dict[str, Any], role: str) -> dict[str, Any]:
    return next(c for c in data["brief"]["contacts"] if c["role"] == role)


async def test_signatory_no_asks_for_the_signatory(life) -> None:
    client, app = life
    await _second_review(client, app)
    opened = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    session_id = opened["session_id"]
    await chat_action(client, session_id, "signatory_answer", {"is_signatory": True})
    answered = await chat_action(client, session_id, "signatory_answer", {"is_signatory": False})
    assert ui_cards(answered, "signatory_question")[0]["payload"]["answered"] == "no"
    rows = ui_cards(answered, "contacts")[0]["payload"]["rows"]
    signatory = next(r for r in rows if r["role"] == "authorized_signatory")
    assert signatory["first_name"] is None and signatory["same_as_primary"] is False
    session = await app.state.session_store.get(session_id)
    assert session.signatory_answer == "no"
    events = app.state.services.audit.events(session_id)
    assert [e["payload"]["answer"] for e in events if e["type"] == "signatory_answered"] == [
        "yes",
        "no",
    ]

    invalid = await chat_action(client, session_id, "signatory_answer", {"is_signatory": "yes"})
    assert ui_cards(invalid, "signatory_question") == []
    assert (await app.state.session_store.get(session_id)).signatory_answer == "no"

    # Answered: opening the link again shows the answer and doesn't ask again.
    again = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    assert [c["payload"]["answered"] for c in _card(again, "signatory_question")] == ["no"]
    assert _card(again, "contacts")[0]["payload"]["signatory_answer"] == "no"


async def test_signatory_answer_needs_an_open_contacts_request(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed())
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    events = await chat_action(client, session_id, "signatory_answer", {"is_signatory": True})
    assert ui_cards(events, "signatory_question") == []
    session = await app.state.session_store.get(session_id)
    assert (session.signatory_answer, session.contacts_draft) == (None, [])
    assert app.state.services.cases.get(reference).tenant_contacts == []
