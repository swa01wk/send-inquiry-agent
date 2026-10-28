"""Cards for a case after submission (L4 §3.5): status, re-upload, contacts, sales data."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.api.cards import dotted_allowed_extensions
from app.api.schemas import (
    CaseRequestRow,
    CaseStatusPayload,
    ContactRow,
    ContactsPayload,
    DocumentUploadPayload,
    SalesDataPayload,
    UiCard,
)
from app.domain.fields import document_label
from app.domain.master import MasterData
from app.domain.models import DocType, InquiryDraft
from app.domain.summary import DraftDocumentRow
from app.policy.config import get_policy
from app.services.status import REQUEST_LABELS, _from_case
from app.workflow.contacts import contacts_blockers
from app.workflow.models import CONTACT_ROLE_LABELS, Case, CaseRequest, CaseStatus, TenantContact

CASE_STATUS_CARD_ID = "case_status"
CONTACTS_CARD_ID = "contacts"
SALES_DATA_CARD_ID = "sales_data"
REUPLOAD_CARD_ID = "documents"

_STAGE_LABELS = {
    "submitted": "Submitted",
    "first_review": "First review",
    "second_review": "Lead — second review",
    "outcome": "Outcome",
}


def _next_step(case: Case) -> str:
    if case.status == CaseStatus.REUPLOAD_REQUESTED:
        return "Re-upload the requested documents, then press Resubmit."
    open_requests = [r for r in case.requests if r.status == "open"]
    if case.status == CaseStatus.SECOND_REVIEW and open_requests:
        return "The leasing team is waiting for the items below."
    if case.status in (CaseStatus.SUBMITTED, CaseStatus.FIRST_REVIEW, CaseStatus.SECOND_REVIEW):
        return "Nothing is needed from you right now; the leasing team is reviewing."
    if case.status == CaseStatus.REJECTED:
        return get_policy().after_rejection
    return "Your details go to the leasing team's system; the proposal stage comes next."


def build_case_status_card(case: Case, *, message_id: str | None = None) -> UiCard:
    status = _from_case(case)
    decision = case.decisions[-1] if case.decisions else None
    outcome: Literal["approved", "rejected"] | None = None
    remarks: str | None = None
    if case.status == CaseStatus.REJECTED and decision:
        outcome, remarks = "rejected", decision.remarks
    elif case.status in (CaseStatus.APPROVED, CaseStatus.SENT_TO_YARDI):
        outcome = "approved"
    payload = CaseStatusPayload(
        reference=case.reference,
        status=status.status,
        stage=status.current_stage,
        stage_label=_STAGE_LABELS[status.current_stage],
        owner_role=status.owner_role,
        last_change=case.last_change,
        open_requests=[
            CaseRequestRow(
                id=r.id,
                kind=r.kind,
                label=REQUEST_LABELS[r.kind],
                remarks=r.remarks,
                doc_types=[d.value for d in r.doc_types],
                requested_at=r.requested_at,
            )
            for r in case.requests
            if r.status == "open"
        ],
        outcome=outcome,
        outcome_remarks=remarks,
        next_step=_next_step(case),
    )
    return UiCard(
        card_id=CASE_STATUS_CARD_ID,
        card_type="case_status",
        message_id=message_id,
        payload=payload.model_dump(mode="json"),
    )


def replaced_since(draft: InquiryDraft, doc_type: DocType, since: datetime) -> bool:
    ref = draft.documents.get(doc_type)
    return ref is not None and ref.uploaded_at > since


def build_reupload_card(
    draft: InquiryDraft, request: CaseRequest, master: MasterData, *, max_mb: int
) -> UiCard:
    """`document_upload` in re-upload mode: only the requested types (L4 §3.5)."""
    del master
    rows = []
    for doc_type in request.doc_types:
        ref = draft.documents.get(doc_type)
        fresh = replaced_since(draft, doc_type, request.requested_at)
        rows.append(
            DraftDocumentRow(
                doc_type=doc_type.value,
                label=document_label(doc_type),
                required=True,
                uploaded=fresh,
                file_name=ref.file_name if fresh and ref else None,
                size_bytes=ref.size_bytes if fresh and ref else None,
            )
        )
    payload = DocumentUploadPayload(
        mode="reupload",
        requested_doc_types=[d.value for d in request.doc_types],
        remarks=request.remarks,
        docs=rows,
        numbers=[],
        required_uploaded=sum(1 for r in rows if r.uploaded),
        required_total=len(rows),
        allowed_extensions=dotted_allowed_extensions(),
        max_mb=max_mb,
    )
    return UiCard(
        card_id=REUPLOAD_CARD_ID, card_type="document_upload", payload=payload.model_dump()
    )


def build_contacts_card(contacts: list[TenantContact], request: CaseRequest | None) -> UiCard:
    policy = get_policy().second_level_contacts
    by_role = {c.role: c for c in contacts}
    rows: list[ContactRow] = []
    for role in [*policy.required, *policy.optional]:
        contact = by_role.get(role)
        if contact is None and role not in policy.required:
            continue
        fields = (
            [contact.first_name, contact.last_name, contact.email, contact.mobile, contact.landline]
            if contact
            else []
        )
        filled = [f for f in fields if f.value not in (None, "")]
        rows.append(
            ContactRow(
                role=role,
                label=CONTACT_ROLE_LABELS[role],
                required=role in policy.required,
                first_name=contact.first_name.value if contact else None,
                last_name=contact.last_name.value if contact else None,
                email=contact.email.value if contact else None,
                phone=(contact.mobile.value or contact.landline.value) if contact else None,
                source=filled[0].source.value if filled and filled[0].source else None,
                confirmed=bool(filled) and all(f.confirmed for f in filled),
                same_as_primary=contact.same_as_primary if contact else False,
            )
        )
    blockers = contacts_blockers(contacts)
    payload = ContactsPayload(
        request_id=request.id if request else None,
        remarks=request.remarks if request else None,
        rows=rows,
        can_submit=not [b for b in blockers if not b.startswith("unconfirmed_contact")],
        blockers=blockers,
    )
    return UiCard(card_id=CONTACTS_CARD_ID, card_type="contacts", payload=payload.model_dump())


def build_sales_data_card(
    draft: InquiryDraft, request: CaseRequest | None, *, max_mb: int
) -> UiCard:
    ref = draft.documents.get(DocType.SALES_DATA)
    fresh = ref is not None and (request is None or ref.uploaded_at > request.requested_at)
    payload = SalesDataPayload(
        request_id=request.id if request else None,
        remarks=request.remarks if request else None,
        uploaded=fresh,
        file_name=ref.file_name if fresh and ref else None,
        size_bytes=ref.size_bytes if fresh and ref else None,
        allowed_extensions=dotted_allowed_extensions(),
        max_mb=max_mb,
    )
    return UiCard(
        card_id=SALES_DATA_CARD_ID, card_type="sales_data_upload", payload=payload.model_dump()
    )


def request_cards(
    case: Case,
    draft: InquiryDraft,
    master: MasterData,
    *,
    max_mb: int,
    contacts: list[TenantContact],
) -> list[UiCard]:
    """The card for each open request (shown when the case chat opens)."""
    cards: list[UiCard] = []
    for request in case.requests:
        if request.status != "open":
            continue
        if request.kind == "reupload":
            cards.append(build_reupload_card(draft, request, master, max_mb=max_mb))
        elif request.kind == "contacts":
            cards.append(build_contacts_card(contacts, request))
        elif request.kind == "sales_data":
            cards.append(build_sales_data_card(draft, request, max_mb=max_mb))
    return cards
