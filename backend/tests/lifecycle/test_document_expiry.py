"""Document expiry at first review (demo feedback §3.4, D6), on the app clock: moving the
simulated clock moves a document from valid to expiring soon to expired."""

from __future__ import annotations

import pytest
from tests.lifecycle.conftest import act, submit_case
from tests.lifecycle.test_document_approval import (
    LEASE_ADMIN,
    brief_doc,
    decide,
    detail,
    reviewed,
)

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]


async def _advance(client, hours: int) -> None:
    response = await client.post("/api/dev/clock/advance", json={"hours": hours})
    assert response.status_code == 200, response.text


async def test_expired_is_refused_with_a_suggested_remark_and_soon_is_approvable(life) -> None:
    """End-of-day check 1: "Expired" with Reject preselected; "Expiring soon" approvable."""
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed(company_days=-30, brand_days=7))
    data = await detail(client, LEASE_ADMIN, reference)
    company = brief_doc(data, "company_profile")
    assert company["expiry_status"] == "expired"
    assert company["suggested_reject_remarks"].startswith("This document expired on ")
    assert company["suggested_reject_remarks"].endswith("Please upload a current one.")
    assert brief_doc(data, "brand_profile")["expiry_status"] == "expiring_soon"
    assert brief_doc(data, "brand_profile")["suggested_reject_remarks"] is None

    refused = await decide(client, reference, "company_profile", "approve_document")
    assert refused.status_code == 400
    assert "expired" in refused.json()["error"]["message"]
    soon = await decide(client, reference, "brand_profile", "approve_document")
    assert soon.status_code == 200, soon.text

    # Nothing changes the case on its own (ADR-R6): the expired one is still pending.
    assert (
        brief_doc(await detail(client, LEASE_ADMIN, reference), "company_profile")["approval"]
        == "pending"
    )
    rejected = await decide(
        client,
        reference,
        "company_profile",
        "reject_document",
        remarks=company["suggested_reject_remarks"],
    )
    assert rejected.status_code == 200
    assert brief_doc(rejected.json(), "company_profile")["suggested_reject_remarks"] is None


async def test_the_simulated_clock_moves_the_status(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed(company_days=20, brand_days=365))
    assert (
        brief_doc(await detail(client, LEASE_ADMIN, reference), "company_profile")["expiry_status"]
        == "valid"
    )
    await _advance(client, 24 * 7)
    assert (
        brief_doc(await detail(client, LEASE_ADMIN, reference), "company_profile")["expiry_status"]
        == "expiring_soon"
    )
    await _advance(client, 24 * 14)
    data = await detail(client, LEASE_ADMIN, reference)
    assert brief_doc(data, "company_profile")["expiry_status"] == "expired"
    refused = await decide(client, reference, "company_profile", "approve_document")
    assert refused.status_code == 400


async def test_a_corrected_date_updates_the_status(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed(company_days=-30))
    data = await detail(client, LEASE_ADMIN, reference)
    future = brief_doc(data, "brand_profile")["expiry"]  # a year ahead
    corrected = await decide(
        client, reference, "company_profile", "confirm_document_expiry", expiry_date=future
    )
    assert corrected.status_code == 200, corrected.text
    company = brief_doc(corrected.json(), "company_profile")
    assert (company["expiry"], company["expiry_status"]) == (future, "valid")
    assert company["expiry_extracted"] != future
    approved = await decide(client, reference, "company_profile", "approve_document")
    assert approved.status_code == 200
    assert (await act(client, LEASE_ADMIN, reference, "approve_first")).status_code == 400
