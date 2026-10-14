"""Document upload endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, UploadFile

from app.api.cards import build_document_upload_card, parse_doc_type
from app.api.deps import get_master_data, get_services, get_session_store, get_settings
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import DeleteDocumentResponse, DocumentResponse, UploadDocumentResponse
from app.config import Settings
from app.domain import draft_ops
from app.domain.master import MasterData
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_document_extension, validate_document_size
from app.services.container import ServiceContainer
from app.services.errors import UploadTooLargeError, UploadValidationError
from app.sessions import SessionStore

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
        ref = services.storage.save(
            session_id,
            parsed,
            filename,
            iter([content]),
            size,
        )
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
    card = build_document_upload_card(
        session.draft,
        master,
        max_mb=settings.max_upload_mb,
    )
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
    if existing is not None:
        services.storage.delete(session_id, parsed, existing.file_id)

    session.draft = draft_ops.remove_document(session.draft, parsed)
    card = build_document_upload_card(
        session.draft,
        master,
        max_mb=settings.max_upload_mb,
    )
    draft = build_draft_summary(session.draft, master, changed_keys=[])
    return DeleteDocumentResponse(card=card, draft=draft)
