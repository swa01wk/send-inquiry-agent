"""Document review service (demo feedback §3.3, day R1): the only place document content is
checked. The Send Inquiry Agent never reads a document itself (golden rule 5).

The real service is a colleague's document review agent (owner and interface to agree,
tracker M4). Until then `MockDocumentReviewService` answers from the file name, so tests and
demos can choose an outcome without real documents:

| File name contains | Company or brand profile expiry |
| --- | --- |
| `expired` | 30 days before today |
| `soon` | 7 days after today |
| anything else | 365 days after today |
| `timeout` / `unavailable` | the service fails like a real outage |

Other document types are returned as `done` with no expiry. Day R3 adds extracted fields.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from app import clock
from app.domain.models import DocType, DocumentRef, DocumentReview
from app.services.errors import ServiceTimeout, ServiceUnavailable

# Documents the review service is asked about (the profiles carry an expiry date).
REVIEWED_DOC_TYPES = frozenset({DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE})

EXPIRED_DAYS_AGO = 30
EXPIRING_SOON_DAYS = 7
VALID_DAYS = 365


class DocumentReviewService(Protocol):
    def review(self, ref: DocumentRef, content: bytes) -> DocumentReview: ...


class MockDocumentReviewService:
    """Deterministic answers from the file name; the content is never read."""

    def review(self, ref: DocumentRef, content: bytes) -> DocumentReview:
        del content  # the mock decides from the name; a real adapter sends the file
        name = ref.file_name.lower()
        if "timeout" in name:
            raise ServiceTimeout("Document review did not answer")
        if "unavailable" in name:
            raise ServiceUnavailable("Document review is unavailable")
        now = clock.now()
        if ref.doc_type not in REVIEWED_DOC_TYPES:
            return DocumentReview(status="done", checked_at=now)
        today = now.date()
        if "expired" in name:
            expiry = today - timedelta(days=EXPIRED_DAYS_AGO)
        elif "soon" in name:
            expiry = today + timedelta(days=EXPIRING_SOON_DAYS)
        else:
            expiry = today + timedelta(days=VALID_DAYS)
        return DocumentReview(status="done", expiry_date=expiry, checked_at=now)
