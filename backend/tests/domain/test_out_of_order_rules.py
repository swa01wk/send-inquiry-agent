"""Out-of-order intake (Nov 2026 manual test): what's left before submit, and space values
written the way people type them."""

from datetime import UTC, datetime

import pytest
from app.domain import validation as v
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import DocType
from app.domain.rules import remaining_steps
from app.domain.summary import build_draft_summary
from tests.domain.conftest import fill_minimal_collectible


def _with_documents(draft):
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    for doc_type, file_id in ((DocType.COMPANY_PROFILE, "co-1"), (DocType.BRAND_PROFILE, "br-1")):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=f"{file_id}.pdf",
            size_bytes=100,
            max_bytes=5 * 1024 * 1024,
            uploaded_at=ts,
        )
    return draft


def _collected():
    return fill_minimal_collectible(new_inquiry_draft(), load_master_data())


def test_gate_needs_the_cr_first() -> None:
    assert remaining_steps(new_inquiry_draft())[0] == "cr"


def test_documents_before_verification_leave_the_email_link_open() -> None:
    # The manual test: mobile verified, documents uploaded, email link never opened.
    draft = _with_documents(_collected())
    draft.mobile_verified = True
    assert remaining_steps(draft) == ["verify_email", "terms"]


def test_only_terms_left_when_everything_else_is_done() -> None:
    draft = _with_documents(_collected())
    draft.email_verified = True
    draft.mobile_verified = True
    assert remaining_steps(draft) == ["terms"]


def test_nothing_left_after_submit_or_for_an_existing_account() -> None:
    submitted = _collected()
    submitted.reference = "GEO-STR-100001"
    existing = new_inquiry_draft()
    existing.cr_status = "existing"
    assert remaining_steps(submitted) == []
    assert remaining_steps(existing) == []


def test_draft_checks_carry_remaining_and_next_step() -> None:
    draft = _with_documents(_collected())
    draft.mobile_verified = True
    checks = build_draft_summary(draft, load_master_data()).checks
    assert checks.remaining == ["verify_email", "terms"]
    assert checks.next_step == "verify_email"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30", 30),
        ("30 sqm", 30),
        ("about 30", 30),
        ("around 30 sq m", 30),
        ("٣٠", 30),
    ],
)
def test_area_written_naturally(raw: str, expected: int) -> None:
    assert v.validate_area_min(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("250,000", 250000),
        ("250k", 250000),
        ("up to 250,000 SAR per year", 250000),
        ("SAR 180,000", 180000),
        (250000, 250000),
    ],
)
def test_rent_written_naturally(raw: str | int, expected: int) -> None:
    assert v.validate_rent_max(raw) == expected


@pytest.mark.parametrize("raw", ["30.5", "thirty", "a lot"])
def test_rent_still_rejects_what_is_not_a_whole_number(raw: str) -> None:
    assert isinstance(v.validate_rent_max(raw), v.ValidationError)


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("lease_periods", "3y", "3y"),
        ("lease_periods", "3 years", "3y"),
        ("lease_periods", "three years", "3y"),
        ("lease_periods", "3-year", "3y"),
        ("rent_periods", "yearly", "yearly"),
        ("rent_periods", "per year", "yearly"),
        ("rent_periods", "Monthly", "monthly"),
        ("rent_periods", "a month", "monthly"),
    ],
)
def test_periods_from_labels_and_common_phrases(kind: str, raw: str, expected: str) -> None:
    result = v.validate_master_id(raw, kind=kind, master=load_master_data(), code="x", label="p")
    assert result == expected


@pytest.mark.parametrize(
    ("kind", "raw"), [("lease_periods", "4 years"), ("rent_periods", "weekly")]
)
def test_periods_not_in_master_data_are_rejected(kind: str, raw: str) -> None:
    result = v.validate_master_id(raw, kind=kind, master=load_master_data(), code="x", label="p")
    assert isinstance(result, v.ValidationError)
