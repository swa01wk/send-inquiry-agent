"""Two review levels (demo feedback §3.2, D4, D14): the Lease Admin acts at first level, the
RLM / RPLM of the product line at final level; nobody else at either. Runs with the
shipped policy (`first_level_review_role: lease_admin`)."""

from __future__ import annotations

import pytest
from app.workflow.machine import REVIEW_LEVEL, REVIEWER_EVENTS, TABLE
from app.workflow.models import CaseStatus
from tests.lifecycle.conftest import STORE_CENTRAL, act, outbox, submit_case

pytestmark = pytest.mark.lease_admin

LEASE_ADMIN_CENTRAL = "lease_admin-central"
LEASE_ADMIN_WESTERN = "lease_admin-western"
LEASE_ADMIN_CENTRAL_EMAIL = "reem.almutairi@cenomi.example"
RLM_CENTRAL_EMAIL = "faisal.alqahtani@cenomi.example"


def _case(app, reference):
    return app.state.services.cases.get(reference)


async def _queue(client, reviewer: str) -> list[str]:
    response = await client.get("/api/review/cases", headers={"X-Reviewer-Id": reviewer})
    assert response.status_code == 200, response.text
    return [c["reference"] for c in response.json()]


def test_every_reviewer_event_has_a_level() -> None:
    reviewer_rows = {key for key, (_to, who) in TABLE.items() if "reviewer" in who}
    assert set(REVIEW_LEVEL) == reviewer_rows
    assert {event for (_s, event) in REVIEW_LEVEL} == REVIEWER_EVENTS
    assert REVIEW_LEVEL[(CaseStatus.FIRST_REVIEW, "approved_first")] == "first"
    assert REVIEW_LEVEL[(CaseStatus.FIRST_REVIEW, "reupload_requested")] == "first"
    assert REVIEW_LEVEL[(CaseStatus.SECOND_REVIEW, "approved")] == "final"


async def test_routing_names_both_levels(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    queue = _case(app, reference).review_queue
    assert queue.first_role == "lease_admin"
    assert queue.role == "rlm_store"
    assert reference in await _queue(client, LEASE_ADMIN_CENTRAL)
    assert reference in await _queue(client, STORE_CENTRAL)
    assert reference not in await _queue(client, LEASE_ADMIN_WESTERN)


async def test_inquiry_for_approval_email_goes_to_the_lease_admin(life) -> None:
    """F7, light version: the Lease Admin gets the email; its link opens the case as her."""
    client, app = life
    reference = await submit_case(client, app)
    assigned = outbox(app, LEASE_ADMIN_CENTRAL_EMAIL, "review_assigned")
    assert len(assigned) == 1
    assert assigned[0]["subject"].startswith("Inquiry for approval:")
    assert f"/review/cases/{reference}?as={LEASE_ADMIN_CENTRAL}" in assigned[0]["body"]
    assert "first review" in assigned[0]["body"]
    assert outbox(app, RLM_CENTRAL_EMAIL, "review_assigned") == []


async def test_first_level_belongs_to_the_lease_admin(life) -> None:
    client, app = life
    reference = await submit_case(client, app)

    refused = await act(client, STORE_CENTRAL, reference, "approve_first")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "not_in_queue"

    other_region = await act(client, LEASE_ADMIN_WESTERN, reference, "approve_first")
    assert other_region.status_code == 404  # not in her queue at all

    detail = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": STORE_CENTRAL}
    )
    assert "approve_first" not in detail.json()["legal_actions"]

    approved = await act(client, LEASE_ADMIN_CENTRAL, reference, "approve_first")
    assert approved.status_code == 200, approved.text
    assert _case(app, reference).status == CaseStatus.SECOND_REVIEW


async def test_final_level_belongs_to_the_rlm(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    assert (await act(client, LEASE_ADMIN_CENTRAL, reference, "approve_first")).status_code == 200

    # The final reviewer is told the case is theirs now.
    final = outbox(app, RLM_CENTRAL_EMAIL, "review_assigned")
    assert len(final) == 1 and "final review" in final[0]["body"]

    refused = await act(client, LEASE_ADMIN_CENTRAL, reference, "request_sales_data")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "not_in_queue"
    lease_admin_view = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": LEASE_ADMIN_CENTRAL}
    )
    assert lease_admin_view.json()["legal_actions"] == []

    allowed = await act(client, STORE_CENTRAL, reference, "request_sales_data", remarks="Please")
    assert allowed.status_code == 200, allowed.text


async def test_brief_and_status_name_the_level_that_is_waiting(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    first = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": LEASE_ADMIN_CENTRAL}
    )
    assert first.json()["brief"]["queue_role"] == "Lease Admin"
    await act(client, LEASE_ADMIN_CENTRAL, reference, "approve_first")
    final = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": STORE_CENTRAL}
    )
    assert final.json()["brief"]["queue_role"] == "Regional Leasing Manager (Store)"
