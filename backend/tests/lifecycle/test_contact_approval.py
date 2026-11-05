"""Per-contact approval and the signatory question (demo feedback §3.5, D8): the backend half
of `rd-contact-approval`. Runs with the shipped policy."""

from __future__ import annotations

from typing import Any

import pytest
from app.workflow.contacts import write_contacts
from app.workflow.models import CaseStatus, TenantContact
from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case, token_from
from tests.lifecycle.test_document_approval import (
    LEASE_ADMIN,
    approve_documents,
    detail,
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


async def test_signatory_yes_billing_rejected_fixed_then_approved(life) -> None:
    """End-of-day check 4 and 5, through the API."""
    client, app = life
    reference = await _second_review(client, app)
    link = outbox(app, APPLICANT, "contacts_request")[0]["links"][0]
    opened = await _open(client, link)
    session_id = opened["session_id"]
    question = _card(opened, "signatory_question")
    assert len(question) == 1
    assert question[0]["payload"]["answered"] is None
    assert question[0]["payload"]["yes_label"] == "Yes, I'm the authorised signatory"
    assert _card(opened, "contacts")[0]["payload"]["signatory_answer"] is None

    answered = await chat_action(client, session_id, "signatory_answer", {"is_signatory": True})
    assert ui_cards(answered, "signatory_question")[0]["payload"]["answered"] == "yes"
    contacts_card = ui_cards(answered, "contacts")[0]["payload"]
    signatory_row = next(r for r in contacts_card["rows"] if r["role"] == "authorized_signatory")
    assert signatory_row["same_as_primary"] is True
    assert contacts_card["signatory_answer"] == "yes"
    session = await app.state.session_store.get(session_id)
    assert session.signatory_answer == "yes"

    await _send(client, app, session_id, [OMAR])
    data = await detail(client, LEASE_ADMIN, reference)
    signatory = _contact(data, "authorized_signatory")
    billing = _contact(data, "billing_contact")
    assert (signatory["approval"], signatory["approved_by"]) == (
        "approved",
        "system:verified_primary",
    )
    assert billing["approval"] == "pending"
    assert {"approve_contact", "reject_contact"} <= set(data["legal_actions"])
    assert len(outbox(app, LEASE_ADMIN_EMAIL, "contacts_received")) == 1

    rlm = await detail(client, STORE_CENTRAL, reference)
    assert rlm["approval_blockers"] == ["contact_not_approved:billing_contact"]
    assert "approve" not in rlm["legal_actions"]
    assert "approve_contact" not in rlm["legal_actions"]
    refused = await act(
        client, STORE_CENTRAL, reference, "approve_contact", contact_id=billing["contact_id"]
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "not_in_queue"

    rejected = await act(
        client,
        LEASE_ADMIN,
        reference,
        "reject_contact",
        contact_id=billing["contact_id"],
        remarks="Please use the finance team's mailbox",
    )
    assert rejected.status_code == 200, rejected.text
    requests = outbox(app, APPLICANT, "contacts_request")
    assert len(requests) == 2
    assert "finance team's mailbox" in requests[-1]["body"]

    # The request opened by the rejection asks only for that role; no signatory question.
    reopened = await _open(client, requests[-1]["links"][0])
    assert _card(reopened, "signatory_question") == []
    card = _card(reopened, "contacts")[0]["payload"]
    assert card["roles"] == ["billing_contact"]
    row = next(r for r in card["rows"] if r["role"] == "billing_contact")
    assert (row["approval"], row["approval_remarks"]) == (
        "rejected",
        "Please use the finance team's mailbox",
    )

    await _send(
        client, app, reopened["session_id"], [{**OMAR, "email": "finance@beanstreet.example"}]
    )
    data = await detail(client, LEASE_ADMIN, reference)
    fixed = _contact(data, "billing_contact")
    assert fixed["approval"] == "pending" and fixed["contact_id"] != billing["contact_id"]
    stale = await act(
        client, LEASE_ADMIN, reference, "approve_contact", contact_id=billing["contact_id"]
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_contact"
    approved = await act(
        client, LEASE_ADMIN, reference, "approve_contact", contact_id=fixed["contact_id"]
    )
    assert approved.status_code == 200, approved.text
    assert "Contact approved: billing contact → second_review" in [
        e["summary"] for e in approved.json()["timeline"]
    ]

    rlm = await detail(client, STORE_CENTRAL, reference)
    assert rlm["approval_blockers"] == []
    assert "approve" in rlm["legal_actions"]
    final = await act(client, STORE_CENTRAL, reference, "approve")
    assert final.status_code == 200, final.text
    assert app.state.services.cases.get(reference).status == CaseStatus.SENT_TO_YARDI


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

    # Answered: opening the link again doesn't ask again.
    again = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    assert _card(again, "signatory_question") == []
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
