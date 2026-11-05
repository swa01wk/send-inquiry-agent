"""Per-document approval through the console API and the case chat (demo feedback §3.4, D5,
D7). Runs with the shipped policy: the Lease Admin decides each document, and first-level
approval waits for them."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from app import clock
from app.domain.models import DocType, DocumentReview, InquiryDraft
from app.workflow.models import CaseStatus
from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case, token_from
from tests.scenarios.helpers import chat_action, ui_cards, upload_document

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]

LEASE_ADMIN = "lease_admin-central"
LEASE_ADMIN_WEST = "lease_admin-western"
PROFILES = ("company_profile", "brand_profile")


def reviewed(
    company_days: int | None = 365, brand_days: int | None = 365
) -> Callable[[InquiryDraft], None]:
    """Give the draft's profiles a document review result: expiry `days` from today (None:
    the review service didn't answer)."""

    def prepare(draft: InquiryDraft) -> None:
        now = clock.now()
        for doc_type, days in (
            (DocType.COMPANY_PROFILE, company_days),
            (DocType.BRAND_PROFILE, brand_days),
        ):
            expiry = None if days is None else now.date() + timedelta(days=days)
            review = DocumentReview(
                status="done" if expiry else "pending", expiry_date=expiry, checked_at=now
            )
            draft.documents[doc_type] = draft.documents[doc_type].model_copy(
                update={"review": review}
            )

    return prepare


async def detail(client, reviewer: str, reference: str) -> dict[str, Any]:
    response = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": reviewer}
    )
    assert response.status_code == 200, response.text
    return response.json()


def brief_doc(data: dict[str, Any], doc_type: str) -> dict[str, Any]:
    return next(d for d in data["brief"]["documents"] if d["doc_type"] == doc_type)


async def decide(
    client, reference: str, doc_type: str, action: str, reviewer: str = LEASE_ADMIN, **extra: Any
):
    file_id = brief_doc(await detail(client, LEASE_ADMIN, reference), doc_type)["file_id"]
    return await act(
        client, reviewer, reference, action, doc_type=doc_type, file_id=file_id, **extra
    )


async def approve_documents(client, reference: str) -> None:
    for doc_type in PROFILES:
        response = await decide(client, reference, doc_type, "approve_document")
        assert response.status_code == 200, response.text


async def test_first_level_waits_until_each_document_is_approved(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed())
    data = await detail(client, LEASE_ADMIN, reference)
    assert data["first_approval_blockers"] == [
        "document_pending:company_profile",
        "document_pending:brand_profile",
    ]
    assert {"approve_first", "approve_document", "reject_document"} <= set(data["legal_actions"])
    company = brief_doc(data, "company_profile")
    assert (company["approval"], company["expiry_status"], company["expiry_tracked"]) == (
        "pending",
        "valid",
        True,
    )
    assert "Approve or reject: Company Profile." in data["brief"]["next_decision_checklist"]

    blocked = await act(client, LEASE_ADMIN, reference, "approve_first")
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "invalid_payload"

    await approve_documents(client, reference)
    data = await detail(client, LEASE_ADMIN, reference)
    assert data["first_approval_blockers"] == []
    assert brief_doc(data, "brand_profile")["decided_by"] == LEASE_ADMIN
    assert "Every document is approved" in " ".join(data["brief"]["next_decision_checklist"])
    assert "Document approved: brand profile → first_review" in [
        e["summary"] for e in data["timeline"]
    ]

    approved = await act(client, LEASE_ADMIN, reference, "approve_first")
    assert approved.status_code == 200, approved.text
    assert app.state.services.cases.get(reference).status == CaseStatus.SECOND_REVIEW


async def test_only_the_lease_admin_of_the_region_decides_documents(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed())
    rlm = await decide(client, reference, "company_profile", "approve_document", STORE_CENTRAL)
    assert rlm.status_code == 403
    assert rlm.json()["error"]["code"] == "not_in_queue"
    west = await decide(client, reference, "company_profile", "approve_document", LEASE_ADMIN_WEST)
    assert west.status_code == 404
    rlm_view = await detail(client, STORE_CENTRAL, reference)
    assert "approve_document" not in rlm_view["legal_actions"]
    assert brief_doc(rlm_view, "company_profile")["approval"] == "pending"


async def test_a_second_tab_cannot_decide_the_same_document_again(life) -> None:
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed())
    first = await decide(client, reference, "brand_profile", "approve_document")
    assert first.status_code == 200
    second = await decide(client, reference, "brand_profile", "reject_document", remarks="Late")
    assert second.status_code == 400
    assert "already approved" in second.json()["error"]["message"]


async def test_reject_reupload_in_the_case_chat_then_approve(life) -> None:
    """End-of-day check 2–3: reject, re-upload with nothing ticked, the new file is pending."""
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed())
    assert (
        await decide(client, reference, "company_profile", "approve_document")
    ).status_code == 200
    rejected = await decide(
        client, reference, "brand_profile", "reject_document", remarks="The logo page is missing"
    )
    assert rejected.status_code == 200
    assert "document_rejected:brand_profile" in rejected.json()["first_approval_blockers"]

    response = await act(client, LEASE_ADMIN, reference, "request_reupload", doc_types=[])
    assert response.status_code == 200, response.text
    request = app.state.services.cases.get(reference).open_request("reupload")
    assert [d.value for d in request.doc_types] == ["brand_profile"]
    assert request.remarks == "Brand Profile: The logo page is missing"
    mail = outbox(app, APPLICANT, "reupload_request")
    assert len(mail) == 1 and "The logo page is missing" in mail[0]["body"]

    opened = await client.post("/api/cases/open", json={"token": token_from(mail[0]["links"][0])})
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["session_id"]
    reupload = next(c for c in opened.json()["cards"] if c["card_type"] == "document_upload")
    assert reupload["payload"]["requested_doc_types"] == ["brand_profile"]

    # The Lease Admin can't approve the requested document while the re-upload is awaited.
    old_file = brief_doc(await detail(client, LEASE_ADMIN, reference), "brand_profile")["file_id"]
    early = await act(
        client,
        LEASE_ADMIN,
        reference,
        "approve_document",
        doc_type="brand_profile",
        file_id=old_file,
    )
    assert early.status_code == 400

    uploaded = await upload_document(client, session_id, "brand_profile", "brand_2026.pdf", b"%PDF")
    assert uploaded["status_code"] == 200
    done = await chat_action(client, session_id, "resubmit_documents")
    assert ui_cards(done, "case_status")[0]["payload"]["stage"] == "first_review"

    data = await detail(client, LEASE_ADMIN, reference)
    brand = brief_doc(data, "brand_profile")
    assert brand["approval"] == "pending" and brand["file_id"] != old_file
    assert brand["expiry_status"] == "valid"  # the mock review answered for the new upload
    assert brief_doc(data, "company_profile")["approval"] == "approved"
    assert data["first_approval_blockers"] == ["document_pending:brand_profile"]

    stale = await act(
        client,
        LEASE_ADMIN,
        reference,
        "approve_document",
        doc_type="brand_profile",
        file_id=old_file,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_file"

    assert (await decide(client, reference, "brand_profile", "approve_document")).status_code == 200
    assert (await act(client, LEASE_ADMIN, reference, "approve_first")).status_code == 200


async def test_review_pending_the_lease_admin_enters_the_date(life) -> None:
    """Failure class: the review service didn't answer; the Lease Admin still decides."""
    client, app = life
    reference = await submit_case(client, app, prepare=reviewed(company_days=None))
    data = await detail(client, LEASE_ADMIN, reference)
    company = brief_doc(data, "company_profile")
    assert (company["review_status"], company["expiry_status"]) == ("pending", "unknown")
    assert "expiry_unconfirmed:company_profile" in data["first_approval_blockers"]
    assert "Confirm the expiry date: Company Profile." in data["brief"]["next_decision_checklist"]

    refused = await decide(client, reference, "company_profile", "approve_document")
    assert refused.status_code == 400
    bad = await decide(
        client, reference, "company_profile", "confirm_document_expiry", expiry_date="soon"
    )
    assert bad.status_code == 400
    future = (clock.now().date() + timedelta(days=200)).isoformat()
    confirmed = await decide(
        client, reference, "company_profile", "confirm_document_expiry", expiry_date=future
    )
    assert confirmed.status_code == 200, confirmed.text
    company = brief_doc(confirmed.json(), "company_profile")
    assert (company["expiry_confirmed"], company["expiry_status"]) == (future, "valid")
    await approve_documents(client, reference)
    assert (await act(client, LEASE_ADMIN, reference, "approve_first")).status_code == 200
