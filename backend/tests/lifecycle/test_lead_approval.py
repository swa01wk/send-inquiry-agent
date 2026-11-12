"""The flow v2 second level (spec flow-v2-alignment §3.7, V6, V11, M24–M26): the final reviewer
assigns the unit and answers "Approve Lead?"; only Yes opens the contacts request, and the
final "Approve Lead" sends the lead to Yardi with the assigned unit. Runs with the shipped
policy."""

from __future__ import annotations

from typing import Any

import pytest
from app.workflow.models import CaseStatus
from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case
from tests.lifecycle.test_contact_approval import OMAR, _card, _open, _send
from tests.lifecycle.test_document_approval import (
    LEASE_ADMIN,
    approve_documents,
    detail,
    reviewed,
)
from tests.scenarios.helpers import chat_action

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin, pytest.mark.lead_approval]

UNIT = {"mall_id": "riyadh-mall-a", "unit_ref": "RMA-G-014", "area_sqm": 95}


async def _qualified(client, app) -> str:
    """Submitted, documents approved, "Tenant Qualified" (first level approved)."""
    reference = await submit_case(client, app, prepare=reviewed())
    await approve_documents(client, reference)
    response = await act(client, LEASE_ADMIN, reference, "approve_first")
    assert response.status_code == 200, response.text
    return reference


async def _lead_approved(client, app) -> str:
    reference = await _qualified(client, app)
    assert (await act(client, STORE_CENTRAL, reference, "assign_unit", **UNIT)).status_code == 200
    approved = await act(client, STORE_CENTRAL, reference, "approve_lead")
    assert approved.status_code == 200, approved.text
    return reference


def _flow(steps: list[dict[str, Any]]) -> list[str]:
    return [f"{s['node']}:{s['outcome']}" if s["outcome"] else s["node"] for s in steps]


async def test_tenant_qualified_opens_no_contacts_request(life) -> None:
    client, app = life
    reference = await _qualified(client, app)
    case = app.state.services.cases.get(reference)
    assert case.status == CaseStatus.SECOND_REVIEW
    assert case.requests == []
    assert outbox(app, APPLICANT, "contacts_request") == []

    data = await detail(client, STORE_CENTRAL, reference)
    assert "assign_unit" in data["legal_actions"]
    assert {"approve_lead", "approve", "request_contacts"}.isdisjoint(data["legal_actions"])
    assert {"reject", "request_sales_data"} <= set(data["legal_actions"])
    assert data["lead_approval_blockers"] == ["unit_not_assigned"]
    assert data["assigned_unit"] is None
    assert [m["id"] for m in data["inquiry_malls"]] == ["riyadh-mall-a"]

    # The first level can't assign the unit or approve the lead.
    refused = await act(client, LEASE_ADMIN, reference, "assign_unit", **UNIT)
    assert refused.status_code == 403
    # The old final approval isn't a row here any more.
    old = await act(client, STORE_CENTRAL, reference, "approve")
    assert old.status_code == 409


async def test_approve_lead_needs_the_unit(life) -> None:
    client, app = life
    reference = await _qualified(client, app)
    refused = await act(client, STORE_CENTRAL, reference, "approve_lead")
    assert refused.status_code == 400
    assert "unit_not_assigned" in refused.json()["error"]["message"]
    assert app.state.services.cases.get(reference).status == CaseStatus.SECOND_REVIEW


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({**UNIT, "mall_id": "jeddah-mall-a"}, "inquiry's malls"),
        ({**UNIT, "mall_id": ""}, "inquiry's malls"),
        ({**UNIT, "unit_ref": "  "}, "unit reference"),
        ({**UNIT, "area_sqm": "big"}, "square metres"),
        ({**UNIT, "area_sqm": 0}, "more than zero"),
    ],
)
async def test_assign_unit_validates(life, payload: dict[str, Any], message: str) -> None:
    client, app = life
    reference = await _qualified(client, app)
    refused = await act(client, STORE_CENTRAL, reference, "assign_unit", **payload)
    assert refused.status_code == 400
    assert message in refused.json()["error"]["message"]
    assert app.state.services.cases.get(reference).assigned_unit is None


async def test_assign_unit_records_and_replaces(life) -> None:
    client, app = life
    reference = await _qualified(client, app)
    first = await act(client, STORE_CENTRAL, reference, "assign_unit", **UNIT)
    assert first.status_code == 200, first.text
    again = await act(
        client, STORE_CENTRAL, reference, "assign_unit", **{**UNIT, "unit_ref": "RMA-G-020"}
    )
    assert again.status_code == 200
    data = await detail(client, STORE_CENTRAL, reference)
    unit = data["assigned_unit"]
    assert (unit["mall_id"], unit["unit_ref"], unit["area_sqm"], unit["by"]) == (
        "riyadh-mall-a",
        "RMA-G-020",
        95,
        STORE_CENTRAL,
    )
    assert data["lead_approval_blockers"] == []
    assert "approve_lead" in data["legal_actions"]
    # The area is optional.
    no_area = await act(
        client, STORE_CENTRAL, reference, "assign_unit", mall_id="riyadh-mall-a", unit_ref="X-1"
    )
    assert no_area.status_code == 200
    assert app.state.services.cases.get(reference).assigned_unit.area_sqm is None


async def test_open_sales_data_request_blocks_approve_lead(life) -> None:
    client, app = life
    reference = await _qualified(client, app)
    await act(client, STORE_CENTRAL, reference, "assign_unit", **UNIT)
    asked = await act(client, STORE_CENTRAL, reference, "request_sales_data", remarks="Monthly")
    assert asked.status_code == 200, asked.text
    data = await detail(client, STORE_CENTRAL, reference)
    assert data["lead_approval_blockers"] == ["sales_data_pending"]
    assert "approve_lead" not in data["legal_actions"]
    refused = await act(client, STORE_CENTRAL, reference, "approve_lead")
    assert refused.status_code == 400

    withdrawn = await act(client, STORE_CENTRAL, reference, "withdraw_request", kind="sales_data")
    assert withdrawn.status_code == 200, withdrawn.text
    assert (await detail(client, STORE_CENTRAL, reference))["lead_approval_blockers"] == []


async def test_approve_lead_opens_contacts_and_cannot_be_rejected(life) -> None:
    client, app = life
    reference = await _lead_approved(client, app)
    case = app.state.services.cases.get(reference)
    assert case.status == CaseStatus.LEAD_APPROVED
    assert [d.outcome for d in case.decisions if d.level == "second"] == ["lead_approved"]
    assert [r.kind for r in case.requests if r.status == "open"] == ["contacts"]
    assert len(outbox(app, APPLICANT, "lead_approved")) == 1
    assert len(outbox(app, APPLICANT, "contacts_request")) == 1

    data = await detail(client, STORE_CENTRAL, reference)
    assert "reject" not in data["legal_actions"]
    assert "approve" not in data["legal_actions"]
    assert data["approval_blockers"] == [
        "open_request:contacts",
        "missing_contact:authorized_signatory",
        "missing_contact:billing_contact",
    ]
    refused = await act(client, STORE_CENTRAL, reference, "reject", remarks="Changed my mind")
    assert refused.status_code == 409


async def test_lead_goes_to_yardi_with_the_unit_after_contacts(life) -> None:
    client, app = life
    reference = await _lead_approved(client, app)
    opened = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    session_id = opened["session_id"]
    await chat_action(client, session_id, "signatory_answer", {"is_signatory": True})
    await _send(client, app, session_id, [OMAR])

    data = await detail(client, STORE_CENTRAL, reference)
    assert data["approval_blockers"] == []
    assert "approve" in data["legal_actions"]
    # V7: no per-contact approval, so no approval state in the console or on the card.
    contacts = data["brief"]["contacts"]
    assert {c["role"] for c in contacts} == {"authorized_signatory", "billing_contact"}
    assert all(c["approval"] is None and c["approved_by"] is None for c in contacts)
    reopened = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    rows = _card(reopened, "contacts")[0]["payload"]["rows"]
    assert rows and all(r["approval"] is None for r in rows)
    final = await act(client, STORE_CENTRAL, reference, "approve")
    assert final.status_code == 200, final.text
    case = app.state.services.cases.get(reference)
    assert case.status == CaseStatus.SENT_TO_YARDI
    lead = app.state.services.yardi.leads[f"lead:{reference}"]["payload"]
    assert lead["assigned_unit"]["unit_ref"] == "RMA-G-014"
    assert lead["assigned_unit"]["area_sqm"] == 95
    assert lead["assigned_unit"]["mall"]


async def test_reject_lead_is_the_no_branch(life) -> None:
    client, app = life
    reference = await _qualified(client, app)
    rejected = await act(client, STORE_CENTRAL, reference, "reject", remarks="No suitable unit")
    assert rejected.status_code == 200, rejected.text
    case = app.state.services.cases.get(reference)
    assert case.status == CaseStatus.REJECTED
    assert outbox(app, APPLICANT, "contacts_request") == []
    assert outbox(app, APPLICANT, "lead_approved") == []


async def test_flow_path_follows_the_chart(life) -> None:
    client, app = life
    reference = await _lead_approved(client, app)
    opened = await _open(client, outbox(app, APPLICANT, "contacts_request")[0]["links"][0])
    await chat_action(client, opened["session_id"], "signatory_answer", {"is_signatory": True})
    await _send(client, app, opened["session_id"], [OMAR])
    assert (await act(client, STORE_CENTRAL, reference, "approve")).status_code == 200

    response = await client.get(f"/api/dev/flow/{reference}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "sent_to_yardi"
    path = body["path"]
    expected = [
        "complete1",
        "ref1",
        "docsok",
        "approve_pt",
        "qualified",
        "rsm",
        "approve_lead",
        "req_contacts",
        "contacts_provide",
        "approve_lead2",
        "create_all",
        "end",
    ]
    positions = [path.index(node) for node in expected]
    assert positions == sorted(positions), path
    steps = _flow(body["steps"])
    assert "approve_lead:yes" in steps
    assert "approve_pt:yes" in steps

    missing = await client.get("/api/dev/flow/GEO-STR-999999")
    assert missing.status_code == 404


@pytest.mark.parametrize(
    ("stage", "status", "reached", "not_yet"),
    [
        ("submitted", "first_review", "vla", "docsok"),
        ("qualified", "second_review", "prod2", "rsm"),
        ("lead_approved", "lead_approved", "contacts_notify", "contacts_provide"),
    ],
)
async def test_flow_seed_applies_the_real_events(
    life, stage: str, status: str, reached: str, not_yet: str
) -> None:
    client, app = life
    seeded = await client.post("/api/dev/flow/seed", json={"stage": stage})
    assert seeded.status_code == 200, seeded.text
    body = seeded.json()
    assert body["status"] == status
    assert body["final_reviewer"]
    flow = (await client.get(f"/api/dev/flow/{body['reference']}")).json()
    assert flow["path"][:2] == ["complete1", "ref1"]
    assert reached in flow["path"] and not_yet not in flow["path"]
