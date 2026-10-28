"""The state machine (M0 §6): every path, the guards and the actor check, as pure calls."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import DocType, DocumentRef
from app.workflow.machine import (
    SYSTEM,
    USER,
    Actor,
    IllegalTransition,
    approval_blockers,
    legal_events,
    transition,
)
from app.workflow.models import Case, CaseStatus, ReviewQueue, TenantContact, WorkflowEvent

T0 = datetime(2026, 10, 30, 9, tzinfo=UTC)
CENTRAL_STORE = Actor(
    kind="reviewer", id="rlm_store-central", role="rlm_store", regions=["central"]
)
WESTERN_STORE = Actor(
    kind="reviewer", id="rlm_store-western", role="rlm_store", regions=["western"]
)
CENTRAL_MEDIA = Actor(
    kind="reviewer", id="rplm_media-central", role="rplm_media", regions=["central"]
)
QUEUE = {"product_line": "store", "region": "central", "role": "rlm_store"}


def _doc(doc_type: DocType, at: datetime, file_id: str = "f") -> DocumentRef:
    return DocumentRef(
        doc_type=doc_type,
        file_id=file_id,
        file_name=f"{doc_type.value}.pdf",
        size_bytes=10,
        uploaded_at=at,
    )


def _case(status: CaseStatus = CaseStatus.SUBMITTED) -> Case:
    draft = new_inquiry_draft()
    draft.documents[DocType.BRAND_PROFILE] = _doc(DocType.BRAND_PROFILE, T0, "old")
    return Case(
        id="GEO-STR-000001",
        reference="GEO-STR-000001",
        session_id="s1",
        status=status,
        draft=draft,
        submitted_at=T0,
        review_queue=ReviewQueue.model_validate(QUEUE) if status != CaseStatus.SUBMITTED else None,
    )


def _go(case: Case, name: str, actor: Actor, minutes: int = 1, **payload: Any) -> Case:
    return transition(
        case,
        WorkflowEvent(name=name, payload=payload),
        actor=actor,
        now=T0 + timedelta(minutes=minutes),
    )


def _contacts() -> list[dict[str, Any]]:
    return [
        TenantContact(role="authorized_signatory").model_dump(mode="json"),
        TenantContact(role="billing_contact").model_dump(mode="json"),
    ]


def test_approve_approve_and_send_to_yardi() -> None:
    case = _go(_case(), "routed", SYSTEM, queue=QUEUE)
    assert case.status == CaseStatus.FIRST_REVIEW
    case = _go(case, "approved_first", CENTRAL_STORE, 2)
    assert case.status == CaseStatus.SECOND_REVIEW
    case = _go(case, "contacts_requested", SYSTEM, 3)
    assert legal_events(case, CENTRAL_STORE).count("approved") == 0  # request open
    case = _go(case, "contacts_provided", USER, 4, contacts=_contacts())
    assert approval_blockers(case) == []
    case = _go(case, "approved", CENTRAL_STORE, 5)
    assert case.status == CaseStatus.APPROVED
    case = _go(case, "yardi_failed", SYSTEM, 6, kind="unavailable")
    assert case.status == CaseStatus.APPROVED and case.yardi.attempts == 1
    case = _go(case, "sent_to_yardi", SYSTEM, 7, lead_ref="YL-000001")
    assert case.status == CaseStatus.SENT_TO_YARDI
    assert case.yardi.lead_ref == "YL-000001"
    assert [e.name for e in case.events] == [
        "routed",
        "approved_first",
        "contacts_requested",
        "contacts_provided",
        "approved",
        "yardi_failed",
        "sent_to_yardi",
    ]
    assert [d.level for d in case.decisions] == ["first", "second"]


@pytest.mark.parametrize("level_status", [CaseStatus.FIRST_REVIEW, CaseStatus.SECOND_REVIEW])
def test_reject_at_either_level(level_status: CaseStatus) -> None:
    case = _case(level_status)
    with pytest.raises(IllegalTransition) as err:
        _go(case, "rejected", CENTRAL_STORE, remarks="  ")
    assert err.value.code == "invalid_payload"
    case = _go(case, "rejected", CENTRAL_STORE, remarks="Not a fit", reason_category="not_a_fit")
    assert case.status == CaseStatus.REJECTED
    assert case.decisions[-1].level == (
        "first" if level_status == CaseStatus.FIRST_REVIEW else "second"
    )
    with pytest.raises(IllegalTransition):
        _go(case, "approved_first", CENTRAL_STORE)  # never reopened


def test_unknown_rejection_category_is_refused() -> None:
    with pytest.raises(IllegalTransition):
        _go(
            _case(CaseStatus.FIRST_REVIEW),
            "rejected",
            CENTRAL_STORE,
            remarks="x",
            reason_category="??",
        )


def test_reupload_loop_needs_every_document_replaced_after_the_request() -> None:
    case = _go(
        _case(CaseStatus.FIRST_REVIEW),
        "reupload_requested",
        CENTRAL_STORE,
        doc_types=["brand_profile", "company_profile"],
        remarks="The brand profile is from 2019; the company profile is unsigned.",
    )
    assert case.status == CaseStatus.REUPLOAD_REQUESTED
    request = case.open_request("reupload")
    assert request and request.doc_types == [DocType.BRAND_PROFILE, DocType.COMPANY_PROFILE]
    old = _doc(DocType.COMPANY_PROFILE, T0, "old-co").model_dump(mode="json")
    new = _doc(DocType.BRAND_PROFILE, T0 + timedelta(minutes=5), "new-br").model_dump(mode="json")
    with pytest.raises(IllegalTransition) as err:
        _go(
            case,
            "documents_resubmitted",
            USER,
            6,
            documents={"brand_profile": new, "company_profile": old},
        )
    assert "company_profile" in err.value.message
    new_co = _doc(DocType.COMPANY_PROFILE, T0 + timedelta(minutes=5), "new-co").model_dump(
        mode="json"
    )
    case = _go(
        case,
        "documents_resubmitted",
        USER,
        6,
        documents={"brand_profile": new, "company_profile": new_co},
    )
    assert case.status == CaseStatus.FIRST_REVIEW
    assert case.draft.documents[DocType.BRAND_PROFILE].file_id == "new-br"
    assert [d.file_id for d in case.document_history] == ["old"]
    assert case.requests[0].status == "fulfilled"


def test_reupload_guards() -> None:
    case = _case(CaseStatus.FIRST_REVIEW)
    for payload in (
        {"doc_types": [], "remarks": "x"},
        {"doc_types": ["brand_profile"], "remarks": ""},
        {"doc_types": ["sales_data"], "remarks": "x"},
        {"doc_types": ["nope"], "remarks": "x"},
    ):
        with pytest.raises(IllegalTransition) as err:
            transition(
                case,
                WorkflowEvent(name="reupload_requested", payload=payload),
                actor=CENTRAL_STORE,
                now=T0,
            )
        assert err.value.code == "invalid_payload"


def test_sales_data_request_and_withdraw() -> None:
    case = _go(
        _case(CaseStatus.SECOND_REVIEW), "sales_data_requested", CENTRAL_STORE, remarks="Last year"
    )
    with pytest.raises(IllegalTransition):
        _go(case, "sales_data_requested", CENTRAL_STORE)  # one open request per kind
    with pytest.raises(IllegalTransition):
        _go(case, "sales_data_provided", USER, 2)  # file required
    doc = _doc(DocType.SALES_DATA, T0 + timedelta(minutes=2)).model_dump(mode="json")
    provided = _go(case, "sales_data_provided", USER, 3, document=doc)
    assert provided.sales_data and provided.requests[0].status == "fulfilled"
    withdrawn = _go(case, "request_withdrawn", CENTRAL_STORE, 3, kind="sales_data")
    assert withdrawn.requests[0].status == "withdrawn"
    with pytest.raises(IllegalTransition):
        _go(withdrawn, "request_withdrawn", CENTRAL_STORE, 4, kind="sales_data")


def test_contacts_need_the_required_roles() -> None:
    case = _go(_case(CaseStatus.SECOND_REVIEW), "contacts_requested", CENTRAL_STORE)
    only_signatory = [TenantContact(role="authorized_signatory").model_dump(mode="json")]
    with pytest.raises(IllegalTransition) as err:
        _go(case, "contacts_provided", USER, 2, contacts=only_signatory)
    assert "billing_contact" in err.value.message


def test_approval_needs_required_contacts_and_no_open_requests() -> None:
    case = _case(CaseStatus.SECOND_REVIEW)
    assert "missing_contact:billing_contact" in approval_blockers(case)
    with pytest.raises(IllegalTransition):
        _go(case, "approved", CENTRAL_STORE)


def test_relink_company_then_brand() -> None:
    case = _case(CaseStatus.SECOND_REVIEW)
    with pytest.raises(IllegalTransition):
        _go(case, "brand_relinked", CENTRAL_STORE, brand_id="YB-2001")  # company first
    case = _go(case, "company_relinked", CENTRAL_STORE, company_id="YC-1001")
    case = _go(case, "brand_relinked", CENTRAL_STORE, 2, brand_id="YB-2001")
    assert (case.yardi.company_id, case.yardi.brand_id) == ("YC-1001", "YB-2001")


# ---- authority (X2) -----------------------------------------------------------------


@pytest.mark.parametrize(
    "actor",
    [WESTERN_STORE, CENTRAL_MEDIA, USER, SYSTEM, Actor(kind="staff", id="customer-care-1")],
)
def test_only_a_reviewer_of_the_queue_can_decide(actor: Actor) -> None:
    case = _case(CaseStatus.FIRST_REVIEW)
    with pytest.raises(IllegalTransition) as err:
        _go(case, "approved_first", actor)
    assert err.value.code in ("not_in_queue", "not_allowed")
    assert legal_events(case, actor) == []


def test_applicant_events_are_the_applicants() -> None:
    case = _go(_case(CaseStatus.SECOND_REVIEW), "contacts_requested", CENTRAL_STORE)
    with pytest.raises(IllegalTransition) as err:
        _go(case, "contacts_provided", CENTRAL_STORE, 2, contacts=_contacts())
    assert err.value.code == "not_allowed"


def test_illegal_transitions() -> None:
    with pytest.raises(IllegalTransition) as err:
        _go(_case(CaseStatus.FIRST_REVIEW), "approved", CENTRAL_STORE)
    assert err.value.code == "illegal_transition"
    with pytest.raises(IllegalTransition):
        _go(_case(CaseStatus.SENT_TO_YARDI), "rejected", CENTRAL_STORE, remarks="late")


def test_legal_actions_per_status() -> None:
    assert sorted(legal_events(_case(CaseStatus.FIRST_REVIEW), CENTRAL_STORE)) == [
        "approved_first",
        "rejected",
        "reupload_requested",
    ]
    second = legal_events(_case(CaseStatus.SECOND_REVIEW), CENTRAL_STORE)
    assert "approved" not in second  # required contacts missing
    assert {"contacts_requested", "sales_data_requested", "rejected", "company_relinked"} <= set(
        second
    )
    assert legal_events(_case(CaseStatus.REJECTED), CENTRAL_STORE) == []


def test_transition_does_not_change_its_input() -> None:
    case = _case(CaseStatus.FIRST_REVIEW)
    _go(case, "approved_first", CENTRAL_STORE)
    assert case.status == CaseStatus.FIRST_REVIEW and case.events == []
