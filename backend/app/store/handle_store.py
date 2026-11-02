"""Persistence for browser session handles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.store.handle_state import HandleState
from app.store.tables import SessionHandleRow


@dataclass
class HandleRecord:
    id: str
    inquiry_id: UUID
    created_at: datetime
    last_seen_at: datetime
    state: HandleState


@dataclass
class MemoryHandleStore:
    _handles: dict[str, HandleRecord] = field(default_factory=dict)

    def get(self, handle_id: str) -> HandleRecord | None:
        return self._handles.get(handle_id)

    def put(self, record: HandleRecord) -> None:
        self._handles[record.id] = record

    def create(
        self,
        *,
        inquiry_id: UUID,
        handle_id: str | None = None,
        now: datetime | None = None,
    ) -> HandleRecord:
        ts = now or datetime.now(tz=UTC)
        handle_id = handle_id or str(uuid.uuid4())
        record = HandleRecord(
            id=handle_id,
            inquiry_id=inquiry_id,
            created_at=ts,
            last_seen_at=ts,
            state=HandleState(),
        )
        self._handles[handle_id] = record
        return record


class PostgresHandleStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def get(self, handle_id: str) -> HandleRecord | None:
        async with self._sessions() as session:
            row = await session.get(SessionHandleRow, UUID(handle_id))
            if row is None:
                return None
            return HandleRecord(
                id=str(row.id),
                inquiry_id=row.inquiry_id,
                created_at=row.last_seen_at,
                last_seen_at=row.last_seen_at,
                state=HandleState.model_validate(row.handle_state or {}),
            )

    async def put(self, record: HandleRecord) -> None:
        async with self._sessions() as session:
            row = await session.get(SessionHandleRow, UUID(record.id))
            if row is None:
                row = SessionHandleRow(
                    id=UUID(record.id),
                    inquiry_id=record.inquiry_id,
                    last_seen_at=record.last_seen_at,
                    handle_state=record.state.model_dump(mode="json"),
                )
                session.add(row)
            else:
                row.inquiry_id = record.inquiry_id
                row.last_seen_at = record.last_seen_at
                row.handle_state = record.state.model_dump(mode="json")
            await session.commit()

    async def create(
        self,
        *,
        inquiry_id: UUID,
        handle_id: str | None = None,
        now: datetime | None = None,
    ) -> HandleRecord:
        ts = now or datetime.now(tz=UTC)
        handle_uuid = UUID(handle_id) if handle_id else uuid.uuid4()
        record = HandleRecord(
            id=str(handle_uuid),
            inquiry_id=inquiry_id,
            created_at=ts,
            last_seen_at=ts,
            state=HandleState(),
        )
        async with self._sessions() as session:
            session.add(
                SessionHandleRow(
                    id=handle_uuid,
                    inquiry_id=inquiry_id,
                    last_seen_at=ts,
                    handle_state=record.state.model_dump(mode="json"),
                )
            )
            await session.commit()
        return record
