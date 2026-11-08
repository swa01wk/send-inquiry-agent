"""Document upload endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile

from app import clock
from app.api.cards import build_document_upload_card, parse_doc_type, scope_card_data
from app.api.case_cards import build_reupload_card, build_sales_data_card
from app.api.deps import get_master_data, get_services, get_session_store, get_settings
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import (
    DeleteDocumentResponse,
    DocumentResponse,
    UiCard,
    UploadDocumentResponse,
)
from app.config import Settings
from app.domain import draft_ops
from app.domain.document_checks import document_mismatches
from app.domain.document_fill import clear_from_document, fill_from_review
from app.domain.master import MasterData
from app.domain.models import (
    NON_INTAKE_DOC_TYPES,
    DocType,
    DocumentRef,
    DocumentReview,
    InquiryDraft,
)
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_document_extension, validate_document_size
from app.gateway import GatewayError
from app.services.container import ServiceContainer
from app.services.document_review import REVIEWED_DOC_TYPES
from app.services.errors import UploadTooLargeError, UploadValidationError
from app.sessions import Session, SessionStore

router = APIRouter(prefix="/api/sessions", tags=["documents"])


@router.post("/{session_id}/documents", response_model=UploadDocumentResponse)
@limiter.limit("60/minute")
async def upload_document(
    request: Request,
    session_id: str,
    doc_type: Annotated[str, Form()],
    file: UploadFile,
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings),
) -> UploadDocumentResponse:
    lease_id = await store.begin_turn(session_id)
    try:
        return await _upload_document(
            session_id,
            parsed_doc_type=doc_type,
            file=file,
            store=store,
            services=services,
            master=master,
            settings=settings,
        )
    finally:
        await store.end_turn(session_id, lease_id)


async def _upload_document(
    session_id: str,
    *,
    parsed_doc_type: str,
    file: UploadFile,
    store: SessionStore,
    services: ServiceContainer,
    master: MasterData,
    settings: Settings,
) -> UploadDocumentResponse:
    parsed = parse_doc_type(parsed_doc_type)
    if parsed is None:
        raise ApiError(
            400,
            "unknown_doc_type",
            "That document type isn't recognised.",
        )

    filename = file.filename or "upload"
    if ext_err := validate_document_extension(filename):
        raise ApiError(400, ext_err.code, ext_err.message)

    content = await file.read()
    size = len(content)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_err := validate_document_size(size, max_bytes):
        raise ApiError(400, size_err.code, size_err.message)

    session = await store.touch(session_id)
    if parsed in NON_INTAKE_DOC_TYPES and session.mode != "case":
        # Sales data is only taken for a reviewer's request after submission (L4 §3.5).
        raise ApiError(400, "unknown_doc_type", "That document type isn't recognised.")

    try:
        ref = services.gateway.call_sync(
            "storage",
            "save",
            services.storage.save,
            session_id,
            parsed,
            filename,
            iter([content]),
            size,
            inquiry_id=session_id,
        )
    except GatewayError as exc:
        raise ApiError(
            503, f"storage_{exc.kind}", "We couldn't store that file. Please try again."
        ) from exc
    except UploadTooLargeError as exc:
        raise ApiError(400, "too_large", str(exc)) from exc
    except UploadValidationError as exc:
        raise ApiError(400, "invalid_extension", str(exc)) from exc

    # Intake only: a profile fills empty fields, and a replaced profile first takes back
    # what it filled (demo feedback §3.7, ADR-R4). A submitted case's draft isn't rewritten.
    intake = session.mode != "case"
    fills = intake and parsed in REVIEWED_DOC_TYPES
    base = clear_from_document(session.draft, parsed) if fills else session.draft
    updated, val_err = draft_ops.add_document(
        base,
        parsed,
        file_id=ref.file_id,
        file_name=ref.file_name,
        size_bytes=ref.size_bytes,
        max_bytes=max_bytes,
        uploaded_at=ref.uploaded_at,
    )
    if val_err is not None:
        services.storage.delete(session_id, parsed, ref.file_id)
        raise ApiError(400, val_err.code, val_err.message)

    filled: list[str] = []
    if parsed in REVIEWED_DOC_TYPES:
        updated = _with_review(updated, parsed, content, services, session_id)
        if fills:
            updated, filled = fill_from_review(updated, parsed, master)
    mismatches = [m.field for m in document_mismatches(updated, master, doc_type=parsed)]
    session.draft = updated
    card = _scoped(_card_for(session, services, master, settings, parsed), session)
    _remember(session, card)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    services.audit.record(
        session_id,
        "document_added",
        actor="user",
        payload={"doc_type": parsed.value, "ext": ext, "size_bytes": ref.size_bytes},
    )
    # Field names only: values from a document stay out of the audit trail.
    if filled:
        services.audit.record(
            session_id,
            "document_fields_filled",
            actor="system",
            payload={"doc_type": parsed.value, "fields": filled},
        )
    if mismatches:
        services.audit.record(
            session_id,
            "document_mismatch",
            actor="system",
            payload={"doc_type": parsed.value, "fields": mismatches},
        )
    await store.save(session)
    draft = build_draft_summary(session.draft, master, changed_keys=filled)
    document = DocumentResponse(
        doc_type=ref.doc_type.value,
        file_id=ref.file_id,
        file_name=ref.file_name,
        size_bytes=ref.size_bytes,
        uploaded_at=ref.uploaded_at,
    )
    return UploadDocumentResponse(
        document=document,
        card=card,
        draft=draft,
        fields_filled=filled,
        mismatches=mismatches,
    )


def _with_review(
    draft: InquiryDraft,
    doc_type: DocType,
    content: bytes,
    services: ServiceContainer,
    session_id: str,
) -> InquiryDraft:
    """Ask the document review service about a company or brand profile (demo feedback §3.3)
    and keep its typed result on the document. A timeout or outage stores `pending`, so the
    upload still succeeds and a reviewer can decide without it. No content is kept or sent
    to the model: only the typed result."""
    ref: DocumentRef = draft.documents[doc_type]
    try:
        review = services.gateway.call_sync(
            "document_review",
            "review",
            services.document_review.review,
            ref,
            content,
            inquiry_id=session_id,
        )
    except GatewayError:
        review = DocumentReview(status="pending", checked_at=clock.now())
    reviewed = draft.model_copy(deep=True)
    reviewed.documents[doc_type] = ref.model_copy(update={"review": review})
    services.audit.record(
        session_id,
        "document_reviewed",
        actor="system",
        payload={
            "doc_type": doc_type.value,
            "status": review.status,
            "has_expiry": review.expiry_date is not None,
        },
    )
    return reviewed


@router.delete("/{session_id}/documents/{doc_type}", response_model=DeleteDocumentResponse)
@limiter.limit("60/minute")
async def delete_document(
    request: Request,
    session_id: str,
    doc_type: str,
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings),
) -> DeleteDocumentResponse:
    lease_id = await store.begin_turn(session_id)
    try:
        return await _delete_document(
            session_id,
            doc_type=doc_type,
            store=store,
            services=services,
            master=master,
            settings=settings,
        )
    finally:
        await store.end_turn(session_id, lease_id)


async def _delete_document(
    session_id: str,
    *,
    doc_type: str,
    store: SessionStore,
    services: ServiceContainer,
    master: MasterData,
    settings: Settings,
) -> DeleteDocumentResponse:
    parsed = parse_doc_type(doc_type)
    if parsed is None:
        raise ApiError(
            400,
            "unknown_doc_type",
            "That document type isn't recognised.",
        )

    session = await store.touch(session_id)
    existing = session.draft.documents.get(parsed)
    if existing is not None and existing.copied_from is None:
        # A document reused from an earlier inquiry (follow-on) still belongs to that
        # inquiry: only this inquiry's reference to it is removed.
        services.storage.delete(session_id, parsed, existing.file_id)

    base = session.draft
    if session.mode != "case" and parsed in REVIEWED_DOC_TYPES:
        base = clear_from_document(base, parsed)  # its filled values go with it (ADR-R4)
    session.draft = draft_ops.remove_document(base, parsed)
    card = _scoped(_card_for(session, services, master, settings, parsed), session)
    _remember(session, card)
    services.audit.record(
        session_id, "document_removed", actor="user", payload={"doc_type": parsed.value}
    )
    await store.save(session)
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return DeleteDocumentResponse(card=card, draft=draft)


def _card_for(
    session: Session,
    services: ServiceContainer,
    master: MasterData,
    settings: Settings,
    doc_type: DocType,
) -> UiCard:
    """The card the upload belongs to: the intake checklist, or in a case chat the
    re-upload or sales-data card for the open request (L4 §3.5)."""
    case = (
        services.cases.get(session.case_id) if session.mode == "case" and session.case_id else None
    )
    if case is not None:
        if doc_type == DocType.SALES_DATA:
            return build_sales_data_card(
                session.draft, case.open_request("sales_data"), max_mb=settings.max_upload_mb
            )
        request = case.open_request("reupload")
        if request is not None:
            return build_reupload_card(
                session.draft, request, master, max_mb=settings.max_upload_mb
            )
    return build_document_upload_card(session.draft, master, max_mb=settings.max_upload_mb)


def _scoped(card: UiCard, session: Session) -> UiCard:
    """The card id for the chat's current inquiry (follow-on inquiries, L3 §3.11)."""
    scoped: UiCard = UiCard.model_validate(scope_card_data(card.model_dump(), session.inquiry_seq))
    return scoped


def _remember(session: Session, card: UiCard) -> None:
    """Keep the latest documents card for resume, attached to its original message."""
    data = card.model_dump()
    previous = session.cards.get(card.card_id)
    if previous is not None and data.get("message_id") is None:
        data["message_id"] = previous.get("message_id")
    session.remember_card(data)
