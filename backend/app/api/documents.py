"""Document upload endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile

from app.api.cards import build_document_upload_card, parse_doc_type, scope_card_data
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
from app.domain.master import MasterData
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_document_extension, validate_document_size
from app.gateway import GatewayError
from app.services.container import ServiceContainer
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
    parsed = parse_doc_type(doc_type)
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

    updated, val_err = draft_ops.add_document(
        session.draft,
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

    session.draft = updated
    card = _scoped(
        build_document_upload_card(
            session.draft,
            master,
            max_mb=settings.max_upload_mb,
        ),
        session,
    )
    _remember(session, card)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    services.audit.record(
        session_id,
        "document_added",
        actor="user",
        payload={"doc_type": parsed.value, "ext": ext, "size_bytes": ref.size_bytes},
    )
    store.save(session)
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    document = DocumentResponse(
        doc_type=ref.doc_type.value,
        file_id=ref.file_id,
        file_name=ref.file_name,
        size_bytes=ref.size_bytes,
        uploaded_at=ref.uploaded_at,
    )
    return UploadDocumentResponse(document=document, card=card, draft=draft)


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

    session.draft = draft_ops.remove_document(session.draft, parsed)
    card = _scoped(
        build_document_upload_card(
            session.draft,
            master,
            max_mb=settings.max_upload_mb,
        ),
        session,
    )
    _remember(session, card)
    services.audit.record(
        session_id, "document_removed", actor="user", payload={"doc_type": parsed.value}
    )
    store.save(session)
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return DeleteDocumentResponse(card=card, draft=draft)


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
