"""Session store: in memory, with restart-safe JSON snapshots (Day 2, L3 capability 7).

When `DATA_DIR` is set, every session is written to `<DATA_DIR>/sessions/<id>.json` after
each turn, action, upload and verification, and all snapshots are loaded at start-up, so
a backend restart mid-inquiry loses nothing. Without `DATA_DIR` (tests, Playwright) the
store is memory only.

A session also keeps what the user saw: the transcript (`transcript`) and the latest
version of each card (`cards`), so `POST /api/sessions/resume` can render the chat
exactly where the user left off. The Postgres store, turn lease and retention arrive in
step 13 (Sprint 1).
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import InquiryDraft
from app.persistence import JsonFile, data_path

logger = logging.getLogger(__name__)

TRANSCRIPT_LIMIT = 200  # messages kept per session; resume shows the last 20


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
    confirm_card_turns: dict[str, int] = field(default_factory=dict)
    turn_index: int = 0
    test_scenario: str | None = None
    script_step: int = 0
    # What the user saw: [{id, role: "user"|"assistant", text}] and the latest card per id.
    transcript: list[dict[str, str]] = field(default_factory=list)
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Which inquiry of this chat is current: 1, then 2, 3… for follow-on inquiries (L3 §3.11).
    inquiry_seq: int = 1
    # The model failed twice in a turn: the user finishes in the cards (L3 §3.14).
    form_mode: bool = False

    def add_message(self, message_id: str, role: str, text: str) -> None:
        self.transcript.append({"id": message_id, "role": role, "text": text})
        if len(self.transcript) > TRANSCRIPT_LIMIT:
            del self.transcript[: len(self.transcript) - TRANSCRIPT_LIMIT]

    def remember_card(self, card: dict[str, Any]) -> None:
        card_id = str(card.get("card_id", ""))
        if card_id:
            self.cards[card_id] = card

    def has_user_messages(self) -> bool:
        return any(m["role"] == "user" for m in self.transcript)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "draft": self.draft.model_dump(mode="json"),
            "created_at": self.created_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "cards_shown": sorted(self.cards_shown),
            "card_counter": self.card_counter,
            "confirm_card_keys": self.confirm_card_keys,
            "confirm_card_turns": self.confirm_card_turns,
            "turn_index": self.turn_index,
            "test_scenario": self.test_scenario,
            "script_step": self.script_step,
            "transcript": self.transcript,
            "cards": self.cards,
            "inquiry_seq": self.inquiry_seq,
            "form_mode": self.form_mode,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Session:
        return cls(
            id=str(raw["id"]),
            draft=InquiryDraft.model_validate(raw["draft"]),
            created_at=datetime.fromisoformat(raw["created_at"]),
            last_seen=datetime.fromisoformat(raw["last_seen"]),
            cards_shown=set(raw.get("cards_shown", [])),
            card_counter=int(raw.get("card_counter", 0)),
            confirm_card_keys=dict(raw.get("confirm_card_keys", {})),
            confirm_card_turns={k: int(v) for k, v in raw.get("confirm_card_turns", {}).items()},
            turn_index=int(raw.get("turn_index", 0)),
            test_scenario=raw.get("test_scenario"),
            script_step=int(raw.get("script_step", 0)),
            transcript=list(raw.get("transcript", [])),
            cards=dict(raw.get("cards", {})),
            inquiry_seq=int(raw.get("inquiry_seq", 1)),
            form_mode=bool(raw.get("form_mode", False)),
        )


_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class SessionStore:
    def __init__(self, ttl_minutes: int, data_dir: str | None = None) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._data_dir = data_dir
        self._sessions: dict[str, Session] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._turn_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()
        self._load_snapshots()

    # ---- persistence -----------------------------------------------------------

    def _file(self, session_id: str) -> JsonFile:
        return JsonFile(data_path(self._data_dir, "sessions", f"{session_id}.json"))

    def _load_snapshots(self) -> None:
        directory = data_path(self._data_dir, "sessions")
        if directory is None or not directory.exists():
            return
        loaded = 0
        for path in sorted(Path(directory).glob("*.json")):
            try:
                session = Session.from_json(JsonFile(path).load({}))
            except Exception:  # a damaged snapshot shouldn't stop the app
                logger.warning("skipping unreadable session snapshot %s", path.name)
                continue
            self._register(session)
            loaded += 1
        if loaded:
            logger.info("restored %d session(s) from %s", loaded, directory)

    def _register(self, session: Session) -> None:
        self._sessions[session.id] = session
        self._locks.setdefault(session.id, asyncio.Lock())
        self._turn_locks.setdefault(session.id, asyncio.Lock())

    def save(self, session: Session) -> None:
        """Write the session's snapshot (no-op without DATA_DIR)."""
        self._file(session.id).save(session.to_json())

    # ---- lifecycle ------------------------------------------------------------

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
            self._register(session)
        return session

    async def get(self, session_id: str) -> Session:
        lock = await self._lock_for(session_id)
        async with lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            if self._is_expired(session):
                self._forget(session_id)
                raise SessionNotFound(session_id)
            return session

    async def touch(self, session_id: str) -> Session:
        session = await self.get(session_id)
        session.last_seen = datetime.now(tz=UTC)
        return session

    async def revive(self, session_id: str) -> Session:
        """A session reached through a signed link, even if idle past the TTL.

        Links (verification, resume) outlive the chat TTL. The session comes back from
        memory or, with DATA_DIR, from its snapshot.
        """
        if not _SAFE_ID.match(session_id):
            raise SessionNotFound(session_id)
        async with self._meta_lock:
            session = self._sessions.get(session_id)
            if session is None:
                raw = self._file(session_id).load(None)
                if raw is None:
                    raise SessionNotFound(session_id)
                session = Session.from_json(raw)
                self._register(session)
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

    def _forget(self, session_id: str) -> None:
        # Memory only: the snapshot stays so a signed link can revive the session.
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)
        self._turn_locks.pop(session_id, None)

    def _is_expired(self, session: Session) -> bool:
        return datetime.now(tz=UTC) - session.last_seen > self._ttl
