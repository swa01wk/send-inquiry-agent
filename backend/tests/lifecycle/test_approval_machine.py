"""Per-document and per-contact decisions in the state machine (demo feedback §3.4, §3.5).

Pure calls, no HTTP. The scenario classes from the architecture assessment (§13.2) each have
a case here: concurrency (two tabs), authorization (wrong role, wrong region), stale context
(a replaced file, a changed contact).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import DocType, DocumentRef, DocumentReview
from app.workflow.documents import current_decisions, document_blockers
from app.workflow.expiry import expired_remarks, expiry_status
from app.workflow.machine import (
    SYSTEM,
    USER,
    Actor,
    IllegalTransition,
    approval_blockers,
    first_approval_blockers,
    legal_events,
    transition,
)
from app.workflow.models import (
    Case,
    CaseStatus,
    DocumentDecision,
    TenantContact,
    WorkflowEvent,
)

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]

T0 = datetime(2026, 11, 5, 9, tzinfo=UTC)
TODAY = T0.date()
QUEUE = {
    "product_line": "store",
    "region": "central",
    "role": "rlm_store",
    "first_role": "lease_admin",
}
LEASE_ADMIN = Actor(
    kind="reviewer", id="lease_admin-central", role="lease_admin", regions=["central"]
)
LEASE_ADMIN_WEST = Actor(
    kind="reviewer", id="lease_admin-western", role="lease_admin", regions=["western"]
)
RLM = Actor(kind="reviewer", id="rlm_store-central", role="rlm_store", regions=["central"])


def _ref(doc_type: DocType, file_id: str, expiry: date | None, at: datetime = T0) -> DocumentRef:
    review = DocumentReview(
        status="done" if expiry else "pending", expiry_date=expiry, checked_at=at
    )
    return DocumentRef(
        doc_type=doc_type,
        file_id=file_id,
        file_name=f"{file_id}.pdf",
        size_bytes=10,
        uploaded_at=at,
        review=review,
    )


def _case(
    company: date | None = TODAY + timedelta(days=365),
    brand: date | None = TODAY + timedelta(days=365),
) -> Case:
    draft = new_inquiry_draft()
    draft.email_verified = draft.mobile_verified = True
    draft.documents[DocType.COMPANY_PROFILE] = _ref(DocType.COMPANY_PROFILE, "co-1", company)
    draft.documents[DocType.BRAND_PROFILE] = _ref(DocType.BRAND_PROFILE, "br-1", brand)
    case = Case(
        id="GEO-STR-000001",
        reference="GEO-STR-000001",
        session_id="s1",
        status=CaseStatus.SUBMITTED,
        draft=draft,
        submitted_at=T0,
    )
    case.document_decisions = current_decisions(case)
    return _go(case, "routed", SYSTEM, queue=QUEUE)


def _go(case: Case, name: str, actor: Actor, minutes: int = 1, **payload: Any) -> Case:
    return transition(
        case,
        WorkflowEvent(name=name, payload=payload),
        actor=actor,
        now=T0 + timedelta(minutes=minutes),
    )


def _doc(case: Case, doc_type: str, action: str, actor: Actor = LEASE_ADMIN, **extra: Any) -> Case:
    file_id = case.draft.documents[DocType(doc_type)].file_id
    return _go(case, action, actor, doc_type=doc_type, file_id=file_id, **extra)


def _approve_documents(case: Case) -> Case:
    for doc_type in ("company_profile", "brand_profile"):
        case = _doc(case, doc_type, "document_approved")
    return case


# ---- expiry status (pure) ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "status"),
    [(-1, "expired"), (0, "expiring_soon"), (13, "expiring_soon"), (14, "valid"), (365, "valid")],
)
def test_expiry_status_against_today(days: int, status: str) -> None:
    decision = DocumentDecision(
        doc_type=DocType.COMPANY_PROFILE,
        file_id="f",
        expiry_extracted=TODAY + timedelta(days=days),
    )
    assert expiry_status(decision, TODAY) == status


def test_the_reviewers_date_wins_and_no_date_is_unknown() -> None:
    decision = DocumentDecision(doc_type=DocType.COMPANY_PROFILE, file_id="f")
    assert expiry_status(decision, TODAY) == "unknown"
    decision.expiry_extracted = TODAY - timedelta(days=3)
    decision.expiry_confirmed = TODAY + timedelta(days=100)
    assert expiry_status(decision, TODAY) == "valid"
    assert expired_remarks(date(2026, 10, 6)) == (
        "This document expired on 06 Oct 2026. Please upload a current one."
    )


# ---- documents ---------------------------------------------------------------------------


def test_first_level_waits_for_every_required_document() -> None:
    case = _case()
    assert first_approval_blockers(case, TODAY) == [
        "document_pending:company_profile",
        "document_pending:brand_profile",
    ]
    with pytest.raises(IllegalTransition) as refused:
        _go(case, "approved_first", LEASE_ADMIN)
    assert refused.value.code == "invalid_payload"
    case = _doc(case, "company_profile", "document_approved")
    assert first_approval_blockers(case, TODAY) == ["document_pending:brand_profile"]
    case = _doc(case, "brand_profile", "document_approved", remarks="Clear")
    decision = case.document_decisions[DocType.BRAND_PROFILE]
    assert (decision.status, decision.by, decision.remarks) == (
        "approved",
        "lease_admin-central",
        "Clear",
    )
    case = _go(case, "approved_first", LEASE_ADMIN)
    assert case.status == CaseStatus.SECOND_REVIEW


def test_an_expired_document_is_refused_and_a_corrected_date_unblocks_it() -> None:
    case = _case(company=TODAY - timedelta(days=30), brand=TODAY + timedelta(days=7))
    with pytest.raises(IllegalTransition, match="expired"):
        _doc(case, "company_profile", "document_approved")
    case = _doc(case, "brand_profile", "document_approved")  # expiring soon: approvable
    case = _doc(
        case,
        "company_profile",
        "document_expiry_confirmed",
        expiry_date=(TODAY + timedelta(days=200)).isoformat(),
    )
    decision = case.document_decisions[DocType.COMPANY_PROFILE]
    assert decision.expiry_confirmed == TODAY + timedelta(days=200)
    assert decision.expiry_confirmed_by == "lease_admin-central"
    case = _doc(case, "company_profile", "document_approved")
    assert first_approval_blockers(case, TODAY) == []


def test_an_unknown_expiry_must_be_confirmed_first() -> None:
    case = _case(company=None)
    assert "expiry_unconfirmed:company_profile" in first_approval_blockers(case, TODAY)
    with pytest.raises(IllegalTransition, match="Confirm the document's expiry date"):
        _doc(case, "company_profile", "document_approved")
    with pytest.raises(IllegalTransition, match="date like"):
        _doc(case, "company_profile", "document_expiry_confirmed", expiry_date="31/03/2027")
    case = _doc(case, "company_profile", "document_expiry_confirmed", expiry_date="2027-03-31")
    case = _doc(case, "company_profile", "document_approved")
    assert case.document_decisions[DocType.COMPANY_PROFILE].status == "approved"


def test_a_past_date_on_an_approved_document_sends_it_back_to_pending() -> None:
    case = _doc(_case(), "company_profile", "document_approved")
    case = _doc(case, "company_profile", "document_expiry_confirmed", expiry_date="2026-01-01")
    assert case.document_decisions[DocType.COMPANY_PROFILE].status == "pending"


def test_two_tabs_approving_the_same_document() -> None:
    case = _doc(_case(), "brand_profile", "document_approved")
    with pytest.raises(IllegalTransition) as second:
        _doc(case, "brand_profile", "document_approved")
    assert second.value.code == "invalid_payload"
    assert "already approved" in second.value.message
    with pytest.raises(IllegalTransition, match="already approved"):
        _doc(case, "brand_profile", "document_rejected", remarks="Wrong file")


def test_rejection_needs_remarks_and_blocks_first_level() -> None:
    case = _case()
    with pytest.raises(IllegalTransition, match="Remarks are required"):
        _doc(case, "brand_profile", "document_rejected")
    case = _doc(case, "brand_profile", "document_rejected", remarks="The logo page is missing")
    assert "document_rejected:brand_profile" in first_approval_blockers(case, TODAY)


def test_reupload_with_nothing_picked_asks_for_the_rejected_documents() -> None:
    case = _doc(_case(), "brand_profile", "document_rejected", remarks="The logo page is missing")
    case = _go(case, "reupload_requested", LEASE_ADMIN, 2, doc_types=[])
    request = case.open_request("reupload")
    assert request is not None
    assert request.doc_types == [DocType.BRAND_PROFILE]
    assert request.remarks == "Brand Profile: The logo page is missing"
    # Nothing rejected and nothing picked: still refused.
    with pytest.raises(IllegalTransition, match="Pick at least one document"):
        _go(_case(), "reupload_requested", LEASE_ADMIN, doc_types=[], remarks="x")


def test_reupload_of_ticked_rejected_documents_uses_their_rejection_remarks() -> None:
    """Re-demo flow 1 (10 Nov): ticking the rejected Brand Profile with no remarks typed
    sends its rejection remarks, as nothing ticked does."""
    case = _doc(_case(), "company_profile", "document_approved")
    case = _doc(case, "brand_profile", "document_rejected", remarks="The logo page is missing")
    ticked = _go(case, "reupload_requested", LEASE_ADMIN, 2, doc_types=["brand_profile"])
    request = ticked.open_request("reupload")
    assert request is not None
    assert request.doc_types == [DocType.BRAND_PROFILE]
    assert request.remarks == "Brand Profile: The logo page is missing"
    # Typed remarks still win.
    typed = _go(
        case, "reupload_requested", LEASE_ADMIN, 2, doc_types=["brand_profile"], remarks="Add logo"
    )
    assert typed.open_request("reupload").remarks == "Add logo"  # type: ignore[union-attr]
    # A ticked document that wasn't rejected still needs remarks.
    with pytest.raises(IllegalTransition, match="Remarks are required"):
        _go(
            case,
            "reupload_requested",
            LEASE_ADMIN,
            2,
            doc_types=["brand_profile", "company_profile"],
        )


def test_a_reupload_starts_a_new_decision_and_refuses_the_old_file() -> None:
    case = _doc(_case(), "company_profile", "document_approved")
    case = _doc(case, "brand_profile", "document_rejected", remarks="Old logo")
    case = _go(case, "reupload_requested", LEASE_ADMIN, 2, doc_types=[])
    # While the re-upload is awaited, the requested document can't be decided.
    with pytest.raises(IllegalTransition, match="re-upload of this document"):
        _go(case, "document_approved", LEASE_ADMIN, 3, doc_type="brand_profile", file_id="br-1")
    new = _ref(DocType.BRAND_PROFILE, "br-2", TODAY + timedelta(days=300), T0 + timedelta(hours=1))
    case = _go(
        case,
        "documents_resubmitted",
        USER,
        90,
        documents={"brand_profile": new.model_dump(mode="json")},
    )
    decision = case.document_decisions[DocType.BRAND_PROFILE]
    assert (decision.file_id, decision.status) == ("br-2", "pending")
    assert decision.expiry_extracted == TODAY + timedelta(days=300)
    assert case.document_decisions[DocType.COMPANY_PROFILE].status == "approved"
    with pytest.raises(IllegalTransition) as stale:
        _go(case, "document_approved", LEASE_ADMIN, 91, doc_type="brand_profile", file_id="br-1")
    assert stale.value.code == "stale_file"
    case = _doc(case, "brand_profile", "document_approved")
    assert _go(case, "approved_first", LEASE_ADMIN, 92).status == CaseStatus.SECOND_REVIEW


def test_only_the_first_level_reviewer_of_the_region_decides_documents() -> None:
    case = _case()
    for actor in (RLM, LEASE_ADMIN_WEST):
        with pytest.raises(IllegalTransition) as refused:
            _doc(case, "company_profile", "document_approved", actor=actor)
        assert refused.value.code == "not_in_queue"
    assert "document_approved" in legal_events(case, LEASE_ADMIN)
    assert "document_approved" not in legal_events(case, RLM)


def test_unknown_documents_and_missing_file_ids_are_refused() -> None:
    case = _case()
    with pytest.raises(IllegalTransition, match="Unknown document type"):
        _go(case, "document_approved", LEASE_ADMIN, doc_type="passport", file_id="x")
    with pytest.raises(IllegalTransition, match="isn't on this case"):
        _go(case, "document_approved", LEASE_ADMIN, doc_type="vat_certificate", file_id="x")
    with pytest.raises(IllegalTransition, match="file id is required"):
        _go(case, "document_approved", LEASE_ADMIN, doc_type="company_profile")


def test_cases_saved_before_decisions_get_them_from_the_current_uploads() -> None:
    case = _case()
    case.document_decisions = {}
    assert document_blockers(case, TODAY) == [
        "document_pending:company_profile",
        "document_pending:brand_profile",
    ]
    case = _doc(case, "company_profile", "document_approved")
    assert set(case.document_decisions) == {DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE}


# ---- contacts ----------------------------------------------------------------------------


def _second_review() -> Case:
    case = _go(_approve_documents(_case()), "approved_first", LEASE_ADMIN, 5)
    return _go(case, "contacts_requested", SYSTEM, 6)


def _contact(role: str, email: str, *, same_as_primary: bool = False, **extra: Any) -> dict:
    contact = TenantContact.model_validate(
        {
            "role": role,
            "first_name": {"value": "Omar", "source": "user", "confirmed": True},
            "last_name": {"value": "Saleh", "source": "user", "confirmed": True},
            "email": {"value": email, "source": "user", "confirmed": True},
            "mobile": {"value": "+966551234567", "source": "user", "confirmed": True},
            "same_as_primary": same_as_primary,
            **extra,
        }
    )
    return contact.model_dump(mode="json")


def _provide(case: Case, minutes: int, billing_email: str = "omar@beanstreet.example") -> Case:
    return _go(
        case,
        "contacts_provided",
        USER,
        minutes,
        contacts=[
            _contact("authorized_signatory", "sara@beanstreet.example", same_as_primary=True),
            # Whatever the applicant's payload claims about approval is ignored.
            _contact("billing_contact", billing_email, approval="approved", approved_by="me"),
        ],
    )


def _by_role(case: Case, role: str) -> TenantContact:
    return next(c for c in case.tenant_contacts if c.role == role)


def test_the_applicant_signatory_is_approved_on_entry_and_billing_waits() -> None:
    case = _provide(_second_review(), 7)
    signatory = _by_role(case, "authorized_signatory")
    billing = _by_role(case, "billing_contact")
    assert (signatory.approval, signatory.approved_by) == ("approved", "system:verified_primary")
    assert (billing.approval, billing.approved_by, billing.added_by) == ("pending", None, "tenant")
    assert billing.contact_id.startswith("ct_") and billing.contact_id != "ct_billing_contact"
    assert approval_blockers(case) == ["contact_not_approved:billing_contact"]
    assert "approved" not in legal_events(case, RLM)
    assert "contact_approved" in legal_events(case, LEASE_ADMIN)
    assert "contact_approved" not in legal_events(case, RLM)


def test_the_lease_admin_approves_a_contact_then_the_rlm_can_approve() -> None:
    case = _provide(_second_review(), 7)
    billing = _by_role(case, "billing_contact")
    with pytest.raises(IllegalTransition) as wrong_role:
        _go(case, "contact_approved", RLM, 8, contact_id=billing.contact_id)
    assert wrong_role.value.code == "not_in_queue"
    case = _go(case, "contact_approved", LEASE_ADMIN, 8, contact_id=billing.contact_id)
    assert _by_role(case, "billing_contact").approved_by == "lease_admin-central"
    with pytest.raises(IllegalTransition, match="already approved"):
        _go(case, "contact_approved", LEASE_ADMIN, 9, contact_id=billing.contact_id)
    assert approval_blockers(case) == []
    assert _go(case, "approved", RLM, 10).status == CaseStatus.APPROVED


def test_a_rejected_contact_opens_a_request_for_that_role() -> None:
    case = _provide(_second_review(), 7)
    billing = _by_role(case, "billing_contact")
    with pytest.raises(IllegalTransition, match="Remarks are required"):
        _go(case, "contact_rejected", LEASE_ADMIN, 8, contact_id=billing.contact_id)
    case = _go(
        case,
        "contact_rejected",
        LEASE_ADMIN,
        8,
        contact_id=billing.contact_id,
        remarks="Use the finance mailbox",
    )
    rejected = _by_role(case, "billing_contact")
    assert (rejected.approval, rejected.approval_remarks) == ("rejected", "Use the finance mailbox")
    request = case.open_request("contacts")
    assert request is not None
    assert request.roles == ["billing_contact"]
    assert request.remarks == "Billing Contact: Use the finance mailbox"
    assert approval_blockers(case) == [
        "open_request:contacts",
        "contact_not_approved:billing_contact",
    ]

    # The tenant fixes it: a new id, pending; the old id is stale.
    fixed = _provide(case, 20, billing_email="finance@beanstreet.example")
    new_billing = _by_role(fixed, "billing_contact")
    assert new_billing.approval == "pending"
    assert new_billing.contact_id != billing.contact_id
    assert _by_role(fixed, "authorized_signatory").approval == "approved"
    with pytest.raises(IllegalTransition) as stale:
        _go(fixed, "contact_approved", LEASE_ADMIN, 21, contact_id=billing.contact_id)
    assert stale.value.code == "stale_contact"
    fixed = _go(fixed, "contact_approved", LEASE_ADMIN, 22, contact_id=new_billing.contact_id)
    assert approval_blockers(fixed) == []


def test_unchanged_approved_contacts_stay_approved_and_changed_ones_go_back() -> None:
    case = _provide(_second_review(), 7)
    billing = _by_role(case, "billing_contact")
    case = _go(case, "contact_approved", LEASE_ADMIN, 8, contact_id=billing.contact_id)
    case = _go(case, "contacts_requested", RLM, 9)
    again = _provide(case, 10)
    assert _by_role(again, "billing_contact").contact_id == billing.contact_id
    assert _by_role(again, "billing_contact").approval == "approved"
    changed = _provide(case, 10, billing_email="new@beanstreet.example")
    assert _by_role(changed, "billing_contact").approval == "pending"


def test_a_second_rejection_adds_its_role_to_the_open_request() -> None:
    case = _go(
        _second_review(),
        "contacts_provided",
        USER,
        7,
        contacts=[
            _contact("authorized_signatory", "sign@beanstreet.example"),
            _contact("billing_contact", "omar@beanstreet.example"),
        ],
    )
    signatory = _by_role(case, "authorized_signatory")
    assert signatory.approval == "pending"  # not the applicant: waits like any contact
    billing = _by_role(case, "billing_contact")
    case = _go(
        case, "contact_rejected", LEASE_ADMIN, 8, contact_id=billing.contact_id, remarks="Typo"
    )
    case = _go(
        case,
        "contact_rejected",
        LEASE_ADMIN,
        9,
        contact_id=signatory.contact_id,
        remarks="Not a director",
    )
    request = case.open_request("contacts")
    assert request is not None
    assert request.roles == ["billing_contact", "authorized_signatory"]
    assert request.remarks.splitlines() == [
        "Billing Contact: Typo",
        "Authorized Signatory: Not a director",
    ]
    assert len([r for r in case.requests if r.kind == "contacts"]) == 2


def test_contacts_saved_before_ids_get_one_per_role() -> None:
    contact = TenantContact.model_validate({"role": "billing_contact"})
    assert contact.contact_id == "ct_billing_contact"
    assert TenantContact.model_validate(contact.model_dump()).contact_id == "ct_billing_contact"
