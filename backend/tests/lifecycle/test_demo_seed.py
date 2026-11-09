"""Day R5: the three seeded demo cases (app/demo_seed.py), through the real handlers."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from app import clock
from app.agent.runtime import AgentRuntime
from app.demo_seed import list_demo_cases, seed_demo
from app.domain.document_checks import document_mismatches
from app.domain.master import load_master_data
from app.domain.models import DocType
from app.main import create_app
from app.workflow.models import CaseStatus
from httpx import ASGITransport, AsyncClient
from tests.lifecycle.conftest import lifecycle_settings, outbox

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]


def _runtime(app) -> AgentRuntime:  # type: ignore[no-untyped-def]
    return AgentRuntime(
        services=app.state.services, master=load_master_data(), settings=app.state.settings
    )


async def test_seed_builds_cases_a_b_and_c(life) -> None:
    _client, app = life
    seeded = await seed_demo(_runtime(app), app.state.session_store)
    assert [c.key for c in seeded] == ["A", "B", "C"]
    by_key = {c.key: app.state.services.cases.get(c.reference) for c in seeded}

    a = by_key["A"]
    assert a is not None and a.status == CaseStatus.FIRST_REVIEW
    company = next(d for d in a.document_decisions if d.doc_type == DocType.COMPANY_PROFILE)
    brand = next(d for d in a.document_decisions if d.doc_type == DocType.BRAND_PROFILE)
    today = clock.now().date()
    assert company.expiry_extracted is not None and company.expiry_extracted < today  # expired
    assert brand.expiry_extracted is not None
    assert today < brand.expiry_extracted < today + timedelta(days=60)  # expiring soon
    assert company.status == "pending" and brand.status == "pending"
    [mismatch] = document_mismatches(a.draft, load_master_data())
    assert (mismatch.field, mismatch.typed, mismatch.document_value) == (
        "company_name",
        "Qahwa House Trading Co.",
        "Qahwa House Holding Company",
    )

    b = by_key["B"]
    assert b is not None and b.status == CaseStatus.SECOND_REVIEW
    roles = {c.role: c.approval for c in b.tenant_contacts}
    assert roles["authorized_signatory"] == "approved"  # the verified primary contact
    assert roles["billing_contact"] == "pending"

    c = by_key["C"]
    assert c is not None and c.status == CaseStatus.SENT_TO_YARDI

    # The seeds have their own personas: nothing lands in the live demo applicant's inbox.
    assert outbox(app, "sara@beanstreet.example") == []
    assert [d.key for d in list_demo_cases(_runtime(app))] == ["A", "B", "C"]


async def test_reset_reseeds_when_demo_seed_is_on(tmp_path: Path) -> None:
    settings = lifecycle_settings(tmp_path, demo_seed=True)
    app = create_app(settings=settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            listed = (await client.get("/api/dev/demo-cases")).json()
            assert [c["key"] for c in listed] == ["A", "B", "C"]  # seeded on start
            before = {c["key"]: c["reference"] for c in listed}

            assert (await client.post("/api/dev/reset")).json() == {"reset": True}
            after = (await client.get("/api/dev/demo-cases")).json()
            assert [c["key"] for c in after] == ["A", "B", "C"]
            assert {c["key"]: c["reference"] for c in after} != before  # fresh cases
            case_b = next(c for c in after if c["key"] == "B")
            assert case_b["status"] == "second_review"
            assert case_b["first_reviewer"] and case_b["final_reviewer"]


async def test_no_seed_without_the_flag(life) -> None:
    client, _app = life
    assert (await client.post("/api/dev/reset")).json() == {"reset": True}
    assert (await client.get("/api/dev/demo-cases")).json() == []
