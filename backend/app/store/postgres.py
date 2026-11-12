"""Postgres inquiry repository (M0 §5.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.draft_ops import new_inquiry_draft
from app.store.errors import InquiryNotFound, TurnInProgress, VersionConflict
from app.store.mapping import inquiry_from_row, row_values_from_inquiry
from app.store.models import (
    Inquiry,
    InquiryStatus,
    SessionState,
    owned_reference,
    settle_status,
)
from app.store.tables import InquiryRow


class PostgresInquiryRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        draft_retention_days: int = 30,
    ) -> None:
        self._sessions = session_factory
        self._draft_retention_days = draft_retention_days

    def _now(self, now: datetime | None) -> datetime:
        return now if now is not None else datetime.now(tz=UTC)

    def _expires_at(self, last_seen: datetime) -> datetime:
        return last_seen + timedelta(days=self._draft_retention_days)

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
        now = self._now(None)
        inquiry_id = uuid.uuid4()
        row = InquiryRow(
            id=inquiry_id,
            status=InquiryStatus.DRAFT.value,
            draft=new_inquiry_draft().model_dump(mode="json"),
            cards_shown=[],
            confirm_card_keys={},
            card_counter=0,
            version=0,
            created_at=now,
            updated_at=now,
            last_seen_at=now,
            expires_at=self._expires_at(now),
            channel=channel,
            case_id=case_id,
            tenant_id=tenant_id,
            staff_id=staff_id,
            session_state=SessionState(mode=mode, created_by=created_by).model_dump(mode="json"),
        )
        async with self._sessions() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return inquiry_from_row(row)

    async def get(self, inquiry_id: UUID) -> Inquiry:
        async with self._sessions() as session:
            row = await session.get(InquiryRow, inquiry_id)
            if row is None:
                raise InquiryNotFound(str(inquiry_id))
            return inquiry_from_row(row)

    async def save(self, inquiry: Inquiry) -> Inquiry:
        to_save = inquiry.model_copy(deep=True)
        to_save.reference = owned_reference(to_save)
        settle_status(to_save)
        values = row_values_from_inquiry(to_save)
        expected = inquiry.version
        async with self._sessions() as session:
            stmt = (
                update(InquiryRow)
                .where(InquiryRow.id == inquiry.id, InquiryRow.version == expected)
                .values(**values, version=InquiryRow.version + 1)
                .returning(InquiryRow)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                await session.rollback()
                existing = await session.get(InquiryRow, inquiry.id)
                if existing is None:
                    raise InquiryNotFound(str(inquiry.id))
                raise VersionConflict
            await session.commit()
            return inquiry_from_row(row)

    async def touch(self, inquiry_id: UUID, *, now: datetime | None = None) -> Inquiry:
        ts = self._now(now)
        expires = self._expires_at(ts)
        async with self._sessions() as session:
            stmt = (
                update(InquiryRow)
                .where(InquiryRow.id == inquiry_id)
                .values(last_seen_at=ts, expires_at=expires)
                .returning(InquiryRow)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                raise InquiryNotFound(str(inquiry_id))
            await session.commit()
            return inquiry_from_row(row)

    async def acquire_turn(self, inquiry_id: UUID, lease_s: int) -> str:
        lease_id = uuid.uuid4().hex
        now = self._now(None)
        lease_until = now + timedelta(seconds=lease_s)
        async with self._sessions() as session:
            stmt = (
                update(InquiryRow)
                .where(
                    InquiryRow.id == inquiry_id,
                    (InquiryRow.turn_lease_until.is_(None)) | (InquiryRow.turn_lease_until < now),
                )
                .values(
                    turn_lease_id=lease_id,
                    turn_lease_until=lease_until,
                )
            )
            result = cast(CursorResult[Any], await session.execute(stmt))
            if result.rowcount == 0:
                await session.rollback()
                row = await session.get(InquiryRow, inquiry_id)
                if row is None:
                    raise InquiryNotFound(str(inquiry_id))
                raise TurnInProgress
            await session.commit()
            return lease_id

    async def renew_turn(self, inquiry_id: UUID, lease_id: str, lease_s: int) -> None:
        lease_until = self._now(None) + timedelta(seconds=lease_s)
        async with self._sessions() as session:
            stmt = (
                update(InquiryRow)
                .where(InquiryRow.id == inquiry_id, InquiryRow.turn_lease_id == lease_id)
                .values(turn_lease_until=lease_until)
            )
            await session.execute(stmt)
            await session.commit()

    async def release_turn(self, inquiry_id: UUID, lease_id: str) -> None:
        async with self._sessions() as session:
            stmt = (
                update(InquiryRow)
                .where(InquiryRow.id == inquiry_id, InquiryRow.turn_lease_id == lease_id)
                .values(turn_lease_id=None, turn_lease_until=None)
            )
            await session.execute(stmt)
            await session.commit()

    async def pending_by_email(self, email: str) -> Inquiry | None:
        """The newest pending inquiry (flow v2) whose verified email is this one."""
        async with self._sessions() as session:
            stmt = (
                select(InquiryRow)
                .where(
                    InquiryRow.status == InquiryStatus.PENDING.value,
                    func.lower(InquiryRow.draft["fields"]["email"]["value"].astext) == email,
                    InquiryRow.draft["email_verified"].astext == "true",
                )
                .order_by(InquiryRow.updated_at.desc())
                .limit(1)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            return inquiry_from_row(row) if row is not None else None

    async def expire_pending(self, now: datetime, ttl: timedelta) -> list[UUID]:
        """Pending inquiries past their TTL since verification → abandoned (FV12)."""
        ts = self._now(now)
        async with self._sessions() as session:
            stmt = select(InquiryRow).where(InquiryRow.status == InquiryStatus.PENDING.value)
            rows = (await session.execute(stmt)).scalars().all()
            ids = [
                row.id
                for row in rows
                if (verified := inquiry_from_row(row).draft.verified_at) is not None
                and ts - max(verified, row.last_seen_at) > ttl
            ]
            if not ids:
                return []
            await session.execute(
                update(InquiryRow)
                .where(InquiryRow.id.in_(ids))
                .values(
                    status=InquiryStatus.ABANDONED.value,
                    turn_lease_id=None,
                    turn_lease_until=None,
                )
            )
            await session.commit()
            return ids

    async def purge_expired(self, now: datetime) -> list[UUID]:
        ts = self._now(now)
        async with self._sessions() as session:
            stmt = select(InquiryRow.id).where(
                InquiryRow.status == InquiryStatus.DRAFT.value, InquiryRow.expires_at < ts
            )
            result = await session.execute(stmt)
            ids = [row[0] for row in result.all()]
            if not ids:
                return []
            await session.execute(
                update(InquiryRow)
                .where(InquiryRow.id.in_(ids))
                .values(
                    status=InquiryStatus.ABANDONED.value,
                    turn_lease_id=None,
                    turn_lease_until=None,
                )
            )
            await session.commit()
            return ids
