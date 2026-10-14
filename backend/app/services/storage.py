"""Document storage."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.domain.models import DocType, DocumentRef
from app.domain.validation import validate_document_extension, validate_document_size
from app.services.errors import UploadTooLargeError, UploadValidationError


class StorageService(Protocol):
    def save(
        self,
        session_id: str,
        doc_type: DocType,
        filename: str,
        stream: Iterator[bytes],
        size: int,
    ) -> DocumentRef: ...

    def delete(self, session_id: str, doc_type: DocType, file_id: str) -> None: ...


class MockStorageService:
    def __init__(self, upload_dir: Path, max_bytes: int) -> None:
        self._upload_dir = upload_dir
        self._max_bytes = max_bytes

    def save(
        self,
        session_id: str,
        doc_type: DocType,
        filename: str,
        stream: Iterator[bytes],
        size: int,
    ) -> DocumentRef:
        if size > self._max_bytes:
            raise UploadTooLargeError("File exceeds size limit.")
        if ext_err := validate_document_extension(filename):
            raise UploadValidationError(ext_err.message)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        file_id = uuid.uuid4().hex
        session_dir = self._upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        target = session_dir / f"{file_id}.{ext}"

        written = 0
        try:
            with target.open("wb") as handle:
                for chunk in stream:
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > self._max_bytes:
                        raise UploadTooLargeError("File exceeds size limit.")
                    handle.write(chunk)
        except Exception:
            if target.exists():
                target.unlink()
            raise

        if size_err := validate_document_size(written, self._max_bytes):
            if target.exists():
                target.unlink()
            raise UploadValidationError(size_err.message)

        return DocumentRef(
            doc_type=doc_type,
            file_id=file_id,
            file_name=filename,
            size_bytes=written,
            uploaded_at=datetime.now(tz=UTC),
        )

    def delete(self, session_id: str, doc_type: DocType, file_id: str) -> None:
        del doc_type
        session_dir = self._upload_dir / session_id
        if not session_dir.exists():
            return
        for path in session_dir.glob(f"{file_id}.*"):
            path.unlink(missing_ok=True)
