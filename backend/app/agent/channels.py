"""Helpers shared by the intake channels (spec §15)."""

from __future__ import annotations

from app.agent.runtime import AgentRuntime
from app.domain.models import (
    NON_INTAKE_DOC_TYPES,
    DocType,
    FieldKey,
    FieldValue,
    InquiryDraft,
    Source,
)
from app.services.tenants import Tenant

STAFF_ROLE_LABELS = {
    "customer_care": "The Cenomi call centre",
    "guest_service": "The mall's Guest Service desk",
}


def started_by_label(runtime: AgentRuntime, staff_id: str | None) -> str:
    """Who started an assisted inquiry, as the applicant should read it."""
    staff = runtime.services.reviewers.get(staff_id) if staff_id else None
    return STAFF_ROLE_LABELS.get(staff.role if staff else "", "The Cenomi call centre")


# A minimal valid PDF: the stand-in for a document on the tenant's file (mock world).
ON_FILE_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def restamp_staff(before: InquiryDraft, after: InquiryDraft) -> tuple[InquiryDraft, list[str]]:
    """In assisted mode the executive typed what the caller said: every value written as
    `user` this turn becomes `staff` (unconfirmed until the applicant confirms it)."""
    changed: list[str] = []
    updated = after.model_copy(deep=True)
    for key in FieldKey:
        new, old = updated.fields[key], before.fields[key]
        if new.source == Source.USER and (new.value != old.value or old.source != Source.USER):
            updated.fields[key] = FieldValue(
                value=new.value, source=Source.STAFF, confirmed=False, evidence=None
            )
            changed.append(key.value)
    return updated, changed


def attach_documents_on_file(
    runtime: AgentRuntime, session_id: str, draft: InquiryDraft, tenant: Tenant
) -> tuple[InquiryDraft, list[str]]:
    """Copy the tenant's documents on file into the inquiry, marked "On file"; the tenant
    can keep or replace each (intake channels §3.4)."""
    updated = draft.model_copy(deep=True)
    attached: list[str] = []
    for document in tenant.documents:
        try:
            doc_type = DocType(document.doc_type)
        except ValueError:
            continue
        if doc_type in NON_INTAKE_DOC_TYPES or doc_type in updated.documents:
            continue
        ref = runtime.services.storage.save(
            session_id, doc_type, document.file_name, iter([ON_FILE_PDF]), len(ON_FILE_PDF)
        )
        updated.documents[doc_type] = ref.model_copy(update={"on_file": True})
        attached.append(doc_type.value)
    return updated, attached
