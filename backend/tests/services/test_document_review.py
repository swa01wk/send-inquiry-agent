"""Document review service contract, against the mock (demo feedback §3.3, D9).

The same checks will run against the real document review agent once its owner shares an
interface (tracker M4): a typed result, an expiry for the profiles, outages as typed errors.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app import clock
from app.domain.models import DocType, DocumentRef, DocumentReview
from app.services.document_review import (
    EXPIRED_DAYS_AGO,
    EXPIRING_SOON_DAYS,
    REVIEWED_DOC_TYPES,
    VALID_DAYS,
    MockDocumentReviewService,
)
from app.services.errors import ServiceTimeout, ServiceUnavailable


def _ref(doc_type: DocType, file_name: str) -> DocumentRef:
    return DocumentRef(
        doc_type=doc_type,
        file_id="f_1",
        file_name=file_name,
        size_bytes=100,
        uploaded_at=datetime(2026, 11, 5, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("file_name", "days"),
    [
        ("company_expired.pdf", -EXPIRED_DAYS_AGO),
        ("brand_soon.pdf", EXPIRING_SOON_DAYS),
        ("company_profile.pdf", VALID_DAYS),
    ],
)
def test_profiles_get_an_expiry_date(file_name: str, days: int) -> None:
    result = MockDocumentReviewService().review(_ref(DocType.COMPANY_PROFILE, file_name), b"%PDF")
    assert isinstance(result, DocumentReview)
    assert result.status == "done"
    assert result.expiry_date == clock.now().date() + timedelta(days=days)


def test_other_documents_get_no_expiry() -> None:
    result = MockDocumentReviewService().review(_ref(DocType.VAT_CERTIFICATE, "vat.pdf"), b"x")
    assert result.status == "done" and result.expiry_date is None


def test_only_the_profiles_are_reviewed() -> None:
    assert frozenset({DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE}) == REVIEWED_DOC_TYPES


@pytest.mark.parametrize(
    ("file_name", "error"),
    [("brand_timeout.pdf", ServiceTimeout), ("brand_unavailable.pdf", ServiceUnavailable)],
)
def test_outages_are_typed_errors(file_name: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        MockDocumentReviewService().review(_ref(DocType.BRAND_PROFILE, file_name), b"x")


def test_result_holds_typed_fields_only() -> None:
    """No raw text anywhere in the result (ADR-R5): only status, a date and typed fields."""
    assert set(DocumentReview.model_fields) == {"status", "expiry_date", "fields", "checked_at"}
    result = MockDocumentReviewService().review(_ref(DocType.BRAND_PROFILE, "b.pdf"), b"SECRET")
    assert "SECRET" not in result.model_dump_json()
