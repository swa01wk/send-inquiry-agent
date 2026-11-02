"""Postgres inquiry repository (M0 §5.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.draft_ops import new_inquiry_draft
from app.store.errors import InquiryNotFound, TurnInProgress, VersionConflict
from app.store.mapping import inquiry_from_row, row_values_from_inquiry
from app.store.models import Inquiry, InquiryStatus, SessionState
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
        if to_save.reference is None and to_save.draft.reference:
            to_save.reference = to_save.draft.reference
        if to_save.status == InquiryStatus.DRAFT and to_save.draft.reference:
            to_save.status = InquiryStatus.SUBMITTED
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
                    (InquiryRow.turn_lease_until.is_(None))
                    | (InquiryRow.turn_lease_until < now),
                )
                .values(
                    turn_lease_id=lease_id,
                    turn_lease_until=lease_until,
                )
            )
            result = await session.execute(stmt)
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

    async def purge_expired(self, now: datetime) -> list[UUID]:
        ts = self._now(now)
        async with self._sessions() as session:
            stmt = (
                select(InquiryRow.id)
                .where(InquiryRow.status == InquiryStatus.DRAFT.value, InquiryRow.expires_at < ts)
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
