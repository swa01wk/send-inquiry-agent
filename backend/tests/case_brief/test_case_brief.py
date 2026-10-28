"""The case brief (L4 §3.6): every line from the case record, nothing invented."""

from datetime import UTC, datetime, timedelta

from app.domain.case_brief import build_case_brief
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import DocType, DocumentRef, Source
from app.workflow.models import Case, CaseRequest, CaseStatus, ReviewQueue

T0 = datetime(2026, 10, 30, 9, tzinfo=UTC)


def _case(status: CaseStatus = CaseStatus.FIRST_REVIEW) -> Case:
    master = load_master_data()
    draft, _w, errors = write_fields(
        new_inquiry_draft(),
        [
            ("company_name", "Bean Street Trading Co.", Source.VERIFIED),
            ("brand_name_en", "Bean Street", Source.USER),
            ("unit_type", "specialty", Source.DERIVED),
            ("malls", ["riyadh-mall-a"], Source.USER),
            ("email", "sara@beanstreet.example", Source.USER),
        ],
        master=master,
        evidence={"unit_type": "specialty coffee kiosk"},
    )
    assert not errors
    draft.cr_status = "skipped"
    draft.documents[DocType.BRAND_PROFILE] = DocumentRef(
        doc_type=DocType.BRAND_PROFILE,
        file_id="b2",
        file_name="brand.pdf",
        size_bytes=9,
        uploaded_at=T0,
    )
    return Case(
        id="GEO-SPC-000001",
        reference="GEO-SPC-000001",
        session_id="s",
        status=status,
        draft=draft,
        submitted_at=T0,
        review_queue=ReviewQueue(product_line="specialty", region="central", role="rplm_specialty"),
        document_history=[
            DocumentRef(
                doc_type=DocType.BRAND_PROFILE,
                file_id="b1",
                file_name="old.pdf",
                size_bytes=9,
                uploaded_at=T0 - timedelta(days=1),
            )
        ],
    )


def test_fields_carry_source_and_evidence() -> None:
    brief = build_case_brief(_case(), load_master_data(), now=T0)
    by_key = {f.key: f for f in brief.fields}
    assert by_key["unit_type"].source == "derived"
    assert by_key["unit_type"].evidence == "specialty coffee kiosk"
    assert by_key["unit_type"].confirmed is False
    assert by_key["company_name"].source == "verified"
    assert by_key["brand_name_en"].source == "user"
    assert brief.mall == "Riyadh Mall A"
    assert brief.queue_role == "Regional Property Leasing Manager (Specialty)"


def test_skipped_cr_and_unconfirmed_values_are_on_the_checklist() -> None:
    brief = build_case_brief(_case(), load_master_data(), now=T0)
    assert brief.cr_status == "skipped"
    text = " ".join(brief.next_decision_checklist)
    assert "CR was skipped" in text
    assert "Unit type" in text and "Company name" in text


def test_documents_with_history() -> None:
    brief = build_case_brief(_case(), load_master_data(), now=T0)
    brand = next(d for d in brief.documents if d.doc_type == "brand_profile")
    assert brand.uploaded and brand.file_id == "b2" and brand.replaced_versions == 1
    company = next(d for d in brief.documents if d.doc_type == "company_profile")
    assert company.uploaded is False and company.required is True


def test_second_review_checklist_from_the_policy() -> None:
    case = _case(CaseStatus.SECOND_REVIEW)
    case.requests.append(
        CaseRequest(id="r1", kind="sales_data", requested_by="x", requested_at=T0, remarks="")
    )
    brief = build_case_brief(case, load_master_data(), now=T0 + timedelta(days=2))
    text = " ".join(brief.next_decision_checklist)
    assert "Billing Contact missing" in text
    assert "Open request: sales data" in text
    assert brief.waiting_on == "applicant"
    assert brief.stage_label == "Lead — second review"


def test_stage_ages() -> None:
    brief = build_case_brief(_case(), load_master_data(), now=T0 + timedelta(days=3))
    assert brief.stage_ages[0].stage == "submitted"
    assert brief.stage_ages[0].days == 3.0
