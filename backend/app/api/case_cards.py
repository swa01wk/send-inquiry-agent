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
    SignatoryQuestionPayload,
    UiCard,
)
from app.domain.fields import document_label
from app.domain.master import MasterData
from app.domain.models import DocType, InquiryDraft
from app.domain.summary import DraftDocumentRow
from app.policy.config import get_policy
from app.services.status import REQUEST_LABELS, _from_case, final_approval_label
from app.workflow.contacts import contacts_blockers
from app.workflow.labels import STATUS_PAGE_STAGES
from app.workflow.models import CONTACT_ROLE_LABELS, Case, CaseRequest, CaseStatus, TenantContact

CASE_STATUS_CARD_ID = "case_status"
CONTACTS_CARD_ID = "contacts"
SALES_DATA_CARD_ID = "sales_data"
REUPLOAD_CARD_ID = "documents"
SIGNATORY_QUESTION_CARD_ID = "signatory_question"

SignatoryAnswer = Literal["yes", "no"]


def as_signatory_answer(value: object) -> SignatoryAnswer | None:
    """A stored answer ("yes" | "no"), or None for anything else."""
    if value == "yes":
        return "yes"
    if value == "no":
        return "no"
    return None


SIGNATORY_PROMPT = "Are you the authorised signatory for your company?"
SIGNATORY_YES = "Yes, I'm the authorised signatory"
SIGNATORY_NO = "No, someone else is"

# Status-page stages, named as on the v2 flowchart (flow v2 §3.5).
_STAGE_LABELS = STATUS_PAGE_STAGES


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
        status_headline=final_approval_label(status.status),
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


def build_signatory_question_card(
    answered: Literal["yes", "no"] | None = None, *, message_id: str | None = None
) -> UiCard:
    """ "Are you the authorised signatory?" when a contacts request opens (demo feedback
    §3.5). The buttons send `signatory_answer {is_signatory}`."""
    payload = SignatoryQuestionPayload(
        prompt=SIGNATORY_PROMPT, yes_label=SIGNATORY_YES, no_label=SIGNATORY_NO, answered=answered
    )
    return UiCard(
        card_id=SIGNATORY_QUESTION_CARD_ID,
        card_type="signatory_question",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def signatory_question_due(request: CaseRequest | None, answer: str | None) -> bool:
    """Ask once per contacts request that covers every role (not one opened for a
    rejected contact), until answered (policy `contacts.ask_signatory`)."""
    return (
        get_policy().contacts.ask_signatory
        and request is not None
        and request.kind == "contacts"
        and not request.roles
        and answer is None
    )


def _sent_approval(case: Case | None, contact: TenantContact | None) -> TenantContact | None:
    """The case's contact for this role if the card still shows what was sent."""
    if case is None or contact is None:
        return None
    sent = next((c for c in case.tenant_contacts if c.role == contact.role), None)
    return sent if sent is not None and sent.values() == contact.values() else None


def build_contacts_card(
    contacts: list[TenantContact],
    request: CaseRequest | None,
    *,
    case: Case | None = None,
    signatory_answer: Literal["yes", "no"] | None = None,
) -> UiCard:
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
        sent = _sent_approval(case, contact)
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
                approval=sent.approval if sent else None,
                approval_remarks=sent.approval_remarks if sent else None,
            )
        )
    blockers = contacts_blockers(contacts)
    payload = ContactsPayload(
        request_id=request.id if request else None,
        remarks=request.remarks if request else None,
        rows=rows,
        can_submit=not [b for b in blockers if not b.startswith("unconfirmed_contact")],
        blockers=blockers,
        roles=list(request.roles) if request else [],
        signatory_answer=signatory_answer,
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
    signatory_answer: Literal["yes", "no"] | None = None,
) -> list[UiCard]:
    """The card for each open request (shown when the case chat opens). A contacts request
    opens with the signatory question until it's answered (§3.5)."""
    cards: list[UiCard] = []
    for request in case.requests:
        if request.status != "open":
            continue
        if request.kind == "reupload":
            cards.append(build_reupload_card(draft, request, master, max_mb=max_mb))
        elif request.kind == "contacts":
            if signatory_question_due(request, signatory_answer):
                cards.append(build_signatory_question_card())
            cards.append(
                build_contacts_card(contacts, request, case=case, signatory_answer=signatory_answer)
            )
        elif request.kind == "sales_data":
            cards.append(build_sales_data_card(draft, request, max_mb=max_mb))
    return cards
