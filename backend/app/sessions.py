"""In-memory session store."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import InquiryDraft


class SessionNotFound(Exception):
    """Raised when a session id is unknown or expired."""


class TurnInProgress(Exception):
    """Raised when a chat turn is already running for this session."""


@dataclass
class Session:
    id: str
    draft: InquiryDraft
    created_at: datetime
    last_seen: datetime
    cards_shown: set[str] = field(default_factory=set)
    card_counter: int = 0
    confirm_card_keys: dict[str, list[str]] = field(default_factory=dict)
    test_scenario: str | None = None
    script_step: int = 0


class SessionStore:
    def __init__(self, ttl_minutes: int) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[str, Session] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._turn_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()

    async def create(self) -> Session:
        session_id = str(uuid.uuid4())
        now = datetime.now(tz=UTC)
        session = Session(
            id=session_id,
            draft=new_inquiry_draft(),
            created_at=now,
            last_seen=now,
        )
        async with self._meta_lock:
            self._sessions[session_id] = session
            self._locks[session_id] = asyncio.Lock()
            self._turn_locks[session_id] = asyncio.Lock()
        return session

    async def get(self, session_id: str) -> Session:
        lock = await self._lock_for(session_id)
        async with lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            if self._is_expired(session):
                del self._sessions[session_id]
                self._locks.pop(session_id, None)
                self._turn_locks.pop(session_id, None)
                raise SessionNotFound(session_id)
            return session

    async def touch(self, session_id: str) -> Session:
        lock = await self._lock_for(session_id)
        async with lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            if self._is_expired(session):
                del self._sessions[session_id]
                self._locks.pop(session_id, None)
                self._turn_locks.pop(session_id, None)
                raise SessionNotFound(session_id)
            session.last_seen = datetime.now(tz=UTC)
            return session

    async def begin_turn(self, session_id: str) -> None:
        async with self._meta_lock:
            turn_lock = self._turn_locks.get(session_id)
            if turn_lock is None:
                raise SessionNotFound(session_id)
        if turn_lock.locked():
            raise TurnInProgress
        await turn_lock.acquire()

    async def end_turn(self, session_id: str) -> None:
        async with self._meta_lock:
            turn_lock = self._turn_locks.get(session_id)
            if turn_lock is None:
                return
        if turn_lock.locked():
            turn_lock.release()

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._meta_lock:
            lock = self._locks.get(session_id)
            if lock is None:
                raise SessionNotFound(session_id)
            return lock

    def _is_expired(self, session: Session) -> bool:
        return datetime.now(tz=UTC) - session.last_seen > self._ttl
