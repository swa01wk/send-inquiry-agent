"""In-memory inquiry repository (M0 §5.2)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.draft_ops import new_inquiry_draft
from app.store.errors import (
    DuplicateReference,
    InquiryNotFound,
    TurnInProgress,
    VersionConflict,
)
from app.store.models import Inquiry, InquiryStatus, SessionState, owned_reference


@dataclass
class _Lease:
    lease_id: str
    until: datetime


@dataclass
class InMemoryInquiryRepository:
    draft_retention_days: int = 30
    _inquiries: dict[UUID, Inquiry] = field(default_factory=dict)
    _leases: dict[UUID, _Lease] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _now(self, now: datetime | None) -> datetime:
        return now if now is not None else datetime.now(tz=UTC)

    def _expires_at(self, last_seen: datetime) -> datetime:
        return last_seen + timedelta(days=self.draft_retention_days)

    async def create(
        self,
        *,
        channel: str = "self_service",
        created_by: str | None = None,
        tenant_id: str | None = None,
        staff_id: str | None = None,
        mode: str = "intake",
        case_id: str | None = None,
    ) -> Inquiry:
        async with self._lock:
            now = self._now(None)
            inquiry_id = uuid.uuid4()
            inquiry = Inquiry(
                id=inquiry_id,
                draft=new_inquiry_draft(),
                created_at=now,
                updated_at=now,
                last_seen_at=now,
                expires_at=self._expires_at(now),
                channel=channel,
                case_id=case_id,
                tenant_id=tenant_id,
                staff_id=staff_id,
                session_state=SessionState(mode=mode, created_by=created_by),
            )
            self._inquiries[inquiry_id] = inquiry
            return inquiry.model_copy(deep=True)

    async def get(self, inquiry_id: UUID) -> Inquiry:
        async with self._lock:
            inquiry = self._inquiries.get(inquiry_id)
            if inquiry is None:
                raise InquiryNotFound(str(inquiry_id))
            return inquiry.model_copy(deep=True)

    async def save(self, inquiry: Inquiry) -> Inquiry:
        async with self._lock:
            stored = self._inquiries.get(inquiry.id)
            if stored is None:
                raise InquiryNotFound(str(inquiry.id))
            if stored.version != inquiry.version:
                raise VersionConflict
            now = self._now(None)
            updated = inquiry.model_copy(deep=True)
            updated.version = stored.version + 1
            updated.updated_at = now
            updated.reference = owned_reference(updated)
            if updated.reference and any(
                other.reference == updated.reference
                for other_id, other in self._inquiries.items()
                if other_id != inquiry.id
            ):
                raise DuplicateReference(updated.reference)
            if updated.status == InquiryStatus.DRAFT and updated.draft.reference:
                updated.status = InquiryStatus.SUBMITTED
            self._inquiries[inquiry.id] = updated
            return updated.model_copy(deep=True)

    async def touch(self, inquiry_id: UUID, *, now: datetime | None = None) -> Inquiry:
        async with self._lock:
            stored = self._inquiries.get(inquiry_id)
            if stored is None:
                raise InquiryNotFound(str(inquiry_id))
            ts = self._now(now)
            updated = stored.model_copy(deep=True)
            updated.last_seen_at = ts
            updated.expires_at = self._expires_at(ts)
            self._inquiries[inquiry_id] = updated
            return updated.model_copy(deep=True)

    async def acquire_turn(self, inquiry_id: UUID, lease_s: int) -> str:
        async with self._lock:
            if inquiry_id not in self._inquiries:
                raise InquiryNotFound(str(inquiry_id))
            now = self._now(None)
            lease = self._leases.get(inquiry_id)
            if lease is not None and lease.until > now:
                raise TurnInProgress
            lease_id = uuid.uuid4().hex
            until = now + timedelta(seconds=lease_s)
            self._leases[inquiry_id] = _Lease(lease_id=lease_id, until=until)
            return lease_id

    async def renew_turn(self, inquiry_id: UUID, lease_id: str, lease_s: int) -> None:
        async with self._lock:
            lease = self._leases.get(inquiry_id)
            if lease is None or lease.lease_id != lease_id:
                return
            now = self._now(None)
            lease.until = now + timedelta(seconds=lease_s)

    async def release_turn(self, inquiry_id: UUID, lease_id: str) -> None:
        async with self._lock:
            lease = self._leases.get(inquiry_id)
            if lease is not None and lease.lease_id == lease_id:
                del self._leases[inquiry_id]

    def bootstrap(self, inquiry: Inquiry) -> None:
        """Restore an inquiry from a JSON snapshot (memory backend only)."""
        self._inquiries[inquiry.id] = inquiry.model_copy(deep=True)

    async def purge_expired(self, now: datetime) -> list[UUID]:
        async with self._lock:
            ts = self._now(now)
            purged: list[UUID] = []
            for inquiry_id, inquiry in list(self._inquiries.items()):
                if inquiry.status != InquiryStatus.DRAFT:
                    continue
                if inquiry.expires_at >= ts:
                    continue
                updated = inquiry.model_copy(deep=True)
                updated.status = InquiryStatus.ABANDONED
                self._inquiries[inquiry_id] = updated
                purged.append(inquiry_id)
                self._leases.pop(inquiry_id, None)
            return purged
