"""Inquiry persistence protocol (M0 §5.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.store.models import Inquiry


class InquiryRepository(Protocol):
    async def create(
        self,
        *,
        channel: str = "self_service",
        created_by: str | None = None,
        tenant_id: str | None = None,
        staff_id: str | None = None,
        mode: str = "intake",
        case_id: str | None = None,
    ) -> Inquiry: ...

    async def get(self, inquiry_id: UUID) -> Inquiry: ...

    async def save(self, inquiry: Inquiry) -> Inquiry: ...

    async def touch(self, inquiry_id: UUID, *, now: datetime | None = None) -> Inquiry: ...

    async def acquire_turn(self, inquiry_id: UUID, lease_s: int) -> str: ...

    async def renew_turn(self, inquiry_id: UUID, lease_id: str, lease_s: int) -> None: ...

    async def release_turn(self, inquiry_id: UUID, lease_id: str) -> None: ...

    async def purge_expired(self, now: datetime) -> list[UUID]: ...

    async def pending_by_email(self, email: str) -> Inquiry | None: ...

    async def expire_pending(self, now: datetime, ttl: timedelta) -> list[UUID]: ...
