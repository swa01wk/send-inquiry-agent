"""Wire service implementations from settings (L3 §3.1: simulated Cenomi)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.audit import AuditLog
from app.clock import Clock, SimulatedClock, SystemClock, install_clock
from app.config import Settings
from app.gateway import FaultPlan, Gateway
from app.notifications import MockNotificationService
from app.proactive.store import AttentionStore
from app.services.call_centre import CallCentreService, MockCallCentreService
from app.services.cr import CrService, MockCrService
from app.services.email_verification import (
    EmailVerificationService,
    MockEmailVerificationService,
)
from app.services.identity import IdentityService, MockIdentityService
from app.services.otp import MockOtpService, OtpService
from app.services.resend import ResendLimiter
from app.services.reviewers import ReviewerDirectory
from app.services.status import MockStatusService, StatusService
from app.services.storage import MockStorageService, StorageService
from app.services.submit import MockSubmitService, SubmitService
from app.services.tenants import OpportunityCatalogue, TenantDirectory
from app.services.yardi import MockYardiService
from app.workflow.store import CaseStore


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
    call_centre: CallCentreService
    cases: CaseStore
    reviewers: ReviewerDirectory
    identity: IdentityService
    yardi: MockYardiService
    attention: AttentionStore
    clock: Clock
    tenants: TenantDirectory
    opportunities: OpportunityCatalogue


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
    cases = CaseStore(data_dir)
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    # Dev tools move a simulated clock (L5 §3.1); otherwise business time is real time.
    clock: Clock = SimulatedClock() if settings.dev_tools else SystemClock()
    install_clock(clock)
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
        status=MockStatusService(submit_service=submit, cases=cases),
        notifications=notifications,
        gateway=Gateway(faults=FaultPlan.parse(settings.mock_faults), audit=audit),
        audit=audit,
        resend=ResendLimiter(data_dir),
        call_centre=MockCallCentreService(
            notifications=notifications,
            inbox_email=settings.call_centre_email,
            data_dir=data_dir,
        ),
        cases=cases,
        reviewers=ReviewerDirectory(),
        identity=MockIdentityService(
            notifications=notifications,
            public_api_url=settings.public_api_url,
            data_dir=data_dir,
        ),
        yardi=MockYardiService(data_dir),
        attention=AttentionStore(data_dir),
        clock=clock,
        tenants=TenantDirectory(),
        opportunities=OpportunityCatalogue(),
    )
