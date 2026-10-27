"""Wire service implementations from settings (L3 §3.1: simulated Cenomi)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.audit import AuditLog
from app.config import Settings
from app.gateway import FaultPlan, Gateway
from app.notifications import MockNotificationService
from app.services.cr import CrService, MockCrService
from app.services.email_verification import (
    EmailVerificationService,
    MockEmailVerificationService,
)
from app.services.otp import MockOtpService, OtpService
from app.services.resend import ResendLimiter
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
    notifications: MockNotificationService
    gateway: Gateway
    audit: AuditLog
    resend: ResendLimiter


def build_services(settings: Settings) -> ServiceContainer:
    if settings.integrations != "mock":
        msg = (
            f"INTEGRATIONS={settings.integrations} isn't available yet: only the simulated "
            "Cenomi systems (mock) exist until Cenomi gives access (L3 §7)."
        )
        raise NotImplementedError(msg)
    data_dir = settings.data_dir
    audit = AuditLog(data_dir)
    notifications = MockNotificationService(data_dir)
    submit = MockSubmitService(data_dir)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    return ServiceContainer(
        cr=MockCrService(),
        otp=MockOtpService(settings.otp_mock_code, notifications=notifications, data_dir=data_dir),
        email_verification=MockEmailVerificationService(
            secret=settings.token_secret,
            notifications=notifications,
            public_base_url=settings.public_base_url,
            ttl_hours=settings.email_link_ttl_hours,
            data_dir=data_dir,
        ),
        storage=MockStorageService(upload_dir=upload_dir, max_bytes=max_bytes),
        submit=submit,
        status=MockStatusService(submit_service=submit),
        notifications=notifications,
        gateway=Gateway(faults=FaultPlan.parse(settings.mock_faults), audit=audit),
        audit=audit,
        resend=ResendLimiter(data_dir),
    )
