"""Flow v2 Send Inquiry sections in the app's order (spec flow-v2-alignment §3.3; day F3)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.draft_ops import add_document, new_inquiry_draft, write_fields
from app.domain.models import DocType, InquiryDraft, Phase, Source
from app.domain.rules import can_submit, compute_phase, remaining_steps
from app.domain.sections import (
    SECTION_ORDER,
    IntakeSection,
    current_section,
    missing_in,
    section_states,
)
from app.domain.summary import build_draft_summary
from app.policy.config import intake_scope
from tests.domain.conftest import fill_minimal_collectible


def _v2(draft: InquiryDraft | None = None) -> InquiryDraft:
    draft = draft or new_inquiry_draft()
    draft.intake_flow = "v2"
    return draft


def _with_documents(draft: InquiryDraft) -> InquiryDraft:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    for doc_type, file_id, name in (
        (DocType.COMPANY_PROFILE, "co-1", "company.pdf"),
        (DocType.BRAND_PROFILE, "br-1", "brand.pdf"),
    ):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=name,
            size_bytes=100,
            max_bytes=5 * 1024 * 1024,
            uploaded_at=ts,
        )
    return draft


def test_sections_follow_the_app_order() -> None:
    assert [s.value for s in SECTION_ORDER] == [
        "company_registration",
        "unit_and_category",
        "basic_info",
        "verification",
        "property_details",
        "terms",
        "documents",
        "review",
    ]


def test_a_new_inquiry_starts_at_company_registration() -> None:
    draft = _v2()
    assert current_section(draft) is IntakeSection.COMPANY_REGISTRATION
    assert remaining_steps(draft)[0] == "cr"


def test_unit_and_category_comes_before_basic_info(master) -> None:
    draft = _v2()
    draft.cr_status = "skipped"
    assert current_section(draft) is IntakeSection.UNIT_AND_CATEGORY
    with intake_scope("v2"):
        # Office is a v2 product line only (§3.3).
        draft, _, errors = write_fields(
            draft,
            [("unit_type", "office", Source.USER), ("sales_category", "fnb_cafe", Source.USER)],
            master=master,
        )
    assert not errors
    assert current_section(draft) is IntakeSection.BASIC_INFO
    assert "email" in missing_in(draft, IntakeSection.BASIC_INFO)


def test_verification_comes_before_property_details(master) -> None:
    draft = _v2(fill_minimal_collectible(new_inquiry_draft(), master))
    assert current_section(draft) is IntakeSection.VERIFICATION
    assert compute_phase(draft) is Phase.VERIFYING
    draft.email_verified = True
    draft.mobile_verified = True
    # Malls are already given: Property Details is done; the terms come next.
    assert current_section(draft) is IntakeSection.TERMS
    assert compute_phase(draft) is Phase.DOCUMENTS


def test_terms_come_before_documents_and_submit(master) -> None:
    draft = _v2(fill_minimal_collectible(new_inquiry_draft(), master))
    draft.email_verified = True
    draft.mobile_verified = True
    draft = _with_documents(draft)
    assert current_section(draft) is IntakeSection.TERMS
    assert "terms_not_accepted" in [b.token for b in can_submit(draft)]
    draft.terms_accepted = True
    assert current_section(draft) is IntakeSection.REVIEW
    assert compute_phase(draft) is Phase.REVIEW


def test_blockers_are_ordered_by_section(master) -> None:
    draft = _v2()
    tokens = [b.token for b in can_submit(draft)]
    assert tokens[0] == "cr_pending"
    unit = tokens.index("missing_field:unit_type")
    first_name = tokens.index("missing_field:first_name")
    malls = tokens.index("missing_field:malls")
    assert unit < first_name < malls


def test_summary_lists_the_sections_for_v2_only(master) -> None:
    v2 = build_draft_summary(_v2(), master, [])
    assert v2.section == "company_registration"
    assert [s.key for s in v2.checks.sections] == [s.value for s in SECTION_ORDER]
    v1 = build_draft_summary(new_inquiry_draft(), master, [])
    assert v1.section is None
    assert not v1.checks.sections


def test_section_states_mark_what_is_done(master) -> None:
    draft = _v2()
    draft.cr_status = "new"
    states = {s.key: s.done for s in section_states(draft)}
    assert states["company_registration"] is True
    assert states["unit_and_category"] is False
