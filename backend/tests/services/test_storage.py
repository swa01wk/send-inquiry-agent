from pathlib import Path

import pytest
from app.domain.models import DocType
from app.services.errors import UploadTooLargeError, UploadValidationError
from app.services.storage import MockStorageService


def test_storage_save_and_delete(tmp_path: Path):
    service = MockStorageService(upload_dir=tmp_path, max_bytes=1024)
    ref = service.save(
        "session-1",
        DocType.COMPANY_PROFILE,
        "profile.pdf",
        iter([b"hello"]),
        size=5,
    )
    assert ref.file_name == "profile.pdf"
    saved = list((tmp_path / "session-1").glob(f"{ref.file_id}.*"))
    assert len(saved) == 1

    service.delete("session-1", DocType.COMPANY_PROFILE, ref.file_id)
    assert not list((tmp_path / "session-1").glob(f"{ref.file_id}.*"))


def test_storage_rejects_oversize_stream_without_partial_file(tmp_path: Path):
    service = MockStorageService(upload_dir=tmp_path, max_bytes=10)
    with pytest.raises(UploadTooLargeError):
        service.save(
            "session-2",
            DocType.BRAND_PROFILE,
            "big.pdf",
            iter([b"0123456789", b"extra"]),
            size=15,
        )
    assert list(tmp_path.rglob("*")) == []


def test_storage_rejects_bad_extension(tmp_path: Path):
    service = MockStorageService(upload_dir=tmp_path, max_bytes=1024)
    with pytest.raises(UploadValidationError):
        service.save(
            "session-3",
            DocType.COMPANY_PROFILE,
            "virus.exe",
            iter([b"x"]),
            size=1,
        )
