"""Human-readable submit blockers for tools."""

from __future__ import annotations

from app.domain.fields import DOCUMENT_DEFINITIONS, FIELD_BY_KEY
from app.domain.models import Blocker, DocType, FieldKey


def blocker_message(blocker: Blocker) -> str:
    token = blocker.token
    if token == "cr_existing":
        return "This CR number already has a Tenant Central account."
    if token == "cr_pending":
        return "CR verification is still pending (verify or skip)."
    if token == "email_not_verified":
        return "Email must be verified with the emailed link."
    if token == "mobile_not_verified":
        return "Mobile must be verified with the code sent by SMS."
    if token == "terms_not_accepted":
        return "Terms and conditions must be accepted on the review card."
    if token.startswith("missing_field:"):
        key = token.split(":", 1)[1]
        if key == "contact":
            return "Mobile or landline is required."
        try:
            return f"{FIELD_BY_KEY[FieldKey(key)].label} is required."
        except ValueError:
            return f"Required field missing: {key}."
    if token.startswith("unconfirmed_field:"):
        key = token.split(":", 1)[1]
        try:
            return f"{FIELD_BY_KEY[FieldKey(key)].label} must be confirmed."
        except ValueError:
            return f"Field must be confirmed: {key}."
    if token.startswith("missing_document:"):
        doc_type = token.split(":", 1)[1]
        try:
            label = next(
                label for dt, label, _req in DOCUMENT_DEFINITIONS if dt == DocType(doc_type)
            )
            return f"Required document missing: {label}."
        except (StopIteration, ValueError):
            return f"Required document missing: {doc_type}."
    return token


def format_blockers(blockers: list[Blocker]) -> str:
    if not blockers:
        return "Nothing blocking submission."
    return "; ".join(blocker_message(b) for b in blockers)
