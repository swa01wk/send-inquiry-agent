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

Other document types are returned as `done` with no expiry.

Day R3 (demo feedback §3.7) adds the fields the service reads from a profile. They come from
`mock_world/document_review.json`, keyed by file name (`company_profile_match.pdf`,
`company_profile_mismatch.pdf`, `brand_profile_match.pdf`, …). Any other file gives no
fields, so existing stories and goldens are unchanged.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

from app import clock
from app.domain.models import DocType, DocumentRef, DocumentReview, ExtractedValue
from app.services.errors import ServiceTimeout, ServiceUnavailable

# Documents the review service is asked about (the profiles carry an expiry date).
REVIEWED_DOC_TYPES = frozenset({DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE})

EXPIRED_DAYS_AGO = 30
EXPIRING_SOON_DAYS = 7
VALID_DAYS = 365

FIELDS_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_world" / "document_review.json"

# The fields each profile can give (demo feedback §3.7). The mock returns only these.
EXTRACTABLE_FIELDS: dict[DocType, tuple[str, ...]] = {
    DocType.COMPANY_PROFILE: ("company_name", "company_address"),
    DocType.BRAND_PROFILE: ("brand_name_en", "sales_category"),
}


def _load_fields(path: Path) -> dict[str, dict[str, str]]:
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    files = raw.get("files", {})
    return {str(name).lower(): dict(values) for name, values in files.items()}


class DocumentReviewService(Protocol):
    def review(self, ref: DocumentRef, content: bytes) -> DocumentReview: ...


class MockDocumentReviewService:
    """Deterministic answers from the file name; the content is never read."""

    def __init__(self, fields_path: Path = FIELDS_PATH) -> None:
        self._fields = _load_fields(fields_path)

    def _fields_for(self, ref: DocumentRef) -> dict[str, ExtractedValue]:
        allowed = EXTRACTABLE_FIELDS.get(ref.doc_type, ())
        values = self._fields.get(ref.file_name.lower(), {})
        return {
            key: ExtractedValue(value=str(value))
            for key, value in values.items()
            if key in allowed and value
        }

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
        return DocumentReview(
            status="done",
            expiry_date=expiry,
            fields=self._fields_for(ref),
            checked_at=now,
        )
