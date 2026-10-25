"""Wire service implementations from settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.services.cr import CrService, MockCrService
from app.services.email_verification import (
    EmailVerificationService,
    MockEmailVerificationService,
)
from app.services.otp import MockOtpService, OtpService
from app.services.status import MockStatusService, StatusService
from app.services.storage import MockStorageService, StorageService
from app.services.submit import MockSubmitService, SubmitService


@dataclass(frozen=True)
class ServiceContainer:
    cr: CrService
    otp: OtpService
    email_verification: EmailVerificationService
    storage: StorageService
    submit: SubmitService
    status: StatusService


def build_services(settings: Settings) -> ServiceContainer:
    submit = MockSubmitService()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    return ServiceContainer(
        cr=MockCrService(),
        otp=MockOtpService(settings.otp_mock_code),
        email_verification=MockEmailVerificationService(),
        storage=MockStorageService(upload_dir=upload_dir, max_bytes=max_bytes),
        submit=submit,
        status=MockStatusService(submit_service=submit),
    )
