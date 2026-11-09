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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domain.models import InquiryDraft
from app.persistence import JsonFile, data_path

logger = logging.getLogger(__name__)

TRANSCRIPT_LIMIT = 200  # messages kept per session; resume shows the last 20


class SessionNotFound(Exception):
    """Raised when a session id is unknown or expired."""


class TurnInProgress(Exception):
    """Raised when a chat turn is already running for this session."""


class TurnConflict(Exception):
    """Optimistic save failed twice; the client should retry the turn."""


@dataclass
class Session:
    id: str
    draft: InquiryDraft
    created_at: datetime
    last_seen: datetime
    inquiry_id: str = ""
    _version: int = field(default=0, repr=False)
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
    # "case": a chat opened from a link after submission, answering the case's requests
    # (L4 §3.5). `case_id` is the reference; `contacts_draft` the contacts being collected.
    mode: str = "intake"
    case_id: str | None = None
    contacts_draft: list[dict[str, Any]] = field(default_factory=list)
    # Intake channel (intake channels §3.8): self_service | assisted | existing_tenant, and
    # who started it (a staff id, a tenant id, or None for the applicant).
    channel: str = "self_service"
    created_by: str | None = None
    tenant_id: str | None = None
    # Set while a call-centre executive (or Guest Service) is driving the chat: the
    # assisted tool allowlist applies and writes are `staff` (§3.2).
    staff_id: str | None = None
    # The application link sent to the applicant (§3.2): where, and the current link's
    # nonce (a resend replaces it, so the old link stops working).
    link_sent_to: str | None = None
    complete_nonce: str | None = None
    # Why this chat ended without a submission, e.g. "redirected_to_sign_in".
    closed: str | None = None
    # Assisted mode, existing CR: which option the executive chose on the card (§3.2).
    existing_cr_choice: str | None = None
    # Case mode, contacts request (demo feedback §3.5): "yes" | "no" to "Are you the
    # authorised signatory?", or None until answered.
    signatory_answer: str | None = None

    @property
    def assisted(self) -> bool:
        return self.staff_id is not None

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
            "inquiry_id": self.inquiry_id or self.id,
            "_version": self._version,
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
            "mode": self.mode,
            "case_id": self.case_id,
            "contacts_draft": self.contacts_draft,
            "channel": self.channel,
            "created_by": self.created_by,
            "tenant_id": self.tenant_id,
            "staff_id": self.staff_id,
            "link_sent_to": self.link_sent_to,
            "complete_nonce": self.complete_nonce,
            "closed": self.closed,
            "existing_cr_choice": self.existing_cr_choice,
            "signatory_answer": self.signatory_answer,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Session:
        sid = str(raw["id"])
        return cls(
            id=sid,
            inquiry_id=str(raw.get("inquiry_id", sid)),
            _version=int(raw.get("_version", 0)),
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
            mode=str(raw.get("mode", "intake")),
            case_id=raw.get("case_id"),
            contacts_draft=list(raw.get("contacts_draft", [])),
            channel=str(raw.get("channel", "self_service")),
            created_by=raw.get("created_by"),
            tenant_id=raw.get("tenant_id"),
            staff_id=raw.get("staff_id"),
            link_sent_to=raw.get("link_sent_to"),
            complete_nonce=raw.get("complete_nonce"),
            closed=raw.get("closed"),
            existing_cr_choice=raw.get("existing_cr_choice"),
            signatory_answer=raw.get("signatory_answer"),
        )


_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


class SessionStore:
    def __init__(
        self,
        repo: Any | None = None,
        *,
        ttl_minutes: int,
        data_dir: str | None = None,
        handle_store: Any | None = None,
        postgres_handles: bool = False,
    ) -> None:
        from app.store.handle_store import HandleRecord, MemoryHandleStore
        from app.store.memory import InMemoryInquiryRepository
        from app.store.repository import InquiryRepository

        if repo is None:
            repo = InMemoryInquiryRepository()
        self._repo: InquiryRepository = repo
        self._HandleRecord = HandleRecord
        self._ttl = timedelta(minutes=ttl_minutes)
        self._data_dir = data_dir
        self._postgres_handles = postgres_handles
        if handle_store is not None:
            self._handles = handle_store
        elif postgres_handles:
            msg = "postgres handle store required when postgres_handles=True"
            raise ValueError(msg)
        else:
            self._handles = MemoryHandleStore()
        self._memory_repo = repo if isinstance(repo, InMemoryInquiryRepository) else None
        self._cache: dict[str, Session] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._turn_locks: dict[str, asyncio.Lock] = {}
        self._meta_lock = asyncio.Lock()
        self._load_snapshots()

    @property
    def inquiry_repo(self) -> Any:
        return self._repo

    def _file(self, session_id: str) -> JsonFile:
        return JsonFile(data_path(self._data_dir, "sessions", f"{session_id}.json"))

    def _load_snapshots(self) -> None:
        if self._memory_repo is None:
            return
        directory = data_path(self._data_dir, "sessions")
        if directory is None or not directory.exists():
            return
        from app.store.session_bridge import handle_from_session, legacy_inquiry_from_session

        loaded = 0
        for path in sorted(Path(directory).glob("*.json")):
            try:
                session = Session.from_json(JsonFile(path).load({}))
            except Exception:
                logger.warning("skipping unreadable session snapshot %s", path.name)
                continue
            inquiry = legacy_inquiry_from_session(session)
            self._memory_repo.bootstrap(inquiry)
            self._handles.put(
                self._HandleRecord(
                    id=session.id,
                    inquiry_id=inquiry.id,
                    created_at=session.created_at,
                    last_seen_at=session.last_seen,
                    state=handle_from_session(session),
                )
            )
            self._register(session)
            loaded += 1
        if loaded:
            logger.info("restored %d session(s) from %s", loaded, directory)

    def _register(self, session: Session) -> None:
        self._cache[session.id] = session
        self._locks.setdefault(session.id, asyncio.Lock())
        self._turn_locks.setdefault(session.id, asyncio.Lock())

    async def _load_session(self, session_id: str) -> Session:
        from app.store.errors import InquiryNotFound as StoreInquiryNotFound
        from app.store.session_bridge import session_from_parts

        if self._postgres_handles:
            handle = await self._handles.get(session_id)
        else:
            handle = self._handles.get(session_id)
        if handle is None:
            raise SessionNotFound(session_id)
        try:
            inquiry = await self._repo.get(handle.inquiry_id)
        except StoreInquiryNotFound as exc:
            raise SessionNotFound(session_id) from exc
        last_seen = handle.last_seen_at
        if self._is_expired_at(last_seen):
            raise SessionNotFound(session_id)
        return session_from_parts(
            handle_id=handle.id,
            inquiry=inquiry,
            handle=handle.state,
            last_seen=handle.last_seen_at,
            created_at=handle.created_at,
        )

    async def _maybe_fork_follow_on(self, session: Session) -> None:
        from app.store.models import InquiryStatus
        from app.store.session_bridge import apply_session_to_inquiry, inquiry_id_for

        inquiry = await self._repo.get(inquiry_id_for(session))
        if inquiry.status != InquiryStatus.SUBMITTED or not inquiry.draft.reference:
            return
        if not session.draft.follow_on_of or session.draft.reference:
            return
        if session.draft.follow_on_of != inquiry.draft.reference:
            return
        new_inquiry = await self._repo.create(
            channel=session.channel,
            created_by=session.created_by,
            tenant_id=session.tenant_id,
            staff_id=session.staff_id,
            mode=session.mode,
            case_id=session.case_id,
        )
        new_inquiry = apply_session_to_inquiry(session, new_inquiry)
        saved = await self._repo.save(new_inquiry)
        session.inquiry_id = str(saved.id)
        session._version = saved.version
        if self._postgres_handles:
            handle = await self._handles.get(session.id)
        else:
            handle = self._handles.get(session.id)
        if handle is not None:
            handle.inquiry_id = saved.id
            if self._postgres_handles:
                await self._handles.put(handle)
            else:
                self._handles.put(handle)

    async def save(self, session: Session, *, retry_on_conflict: bool = True) -> None:
        from app.store.errors import VersionConflict as StoreVersionConflict

        try:
            await self._save_once(session)
        except StoreVersionConflict:
            if not retry_on_conflict:
                raise TurnConflict from None
            fresh = await self._load_session(session.id)
            session._version = fresh._version
            try:
                await self._save_once(session)
            except StoreVersionConflict as exc:
                raise TurnConflict from exc

    async def _save_once(self, session: Session) -> None:  # noqa: PLR0912
        from app.store.session_bridge import (
            apply_session_to_inquiry,
            handle_from_session,
            inquiry_id_for,
        )

        await self._maybe_fork_follow_on(session)
        inquiry = await self._repo.get(inquiry_id_for(session))
        inquiry.version = session._version
        to_save = apply_session_to_inquiry(session, inquiry)
        saved = await self._repo.save(to_save)
        session._version = saved.version
        if self._postgres_handles:
            handle = await self._handles.get(session.id)
        else:
            handle = self._handles.get(session.id)
        if handle is not None:
            handle.state = handle_from_session(session)
            handle.last_seen_at = session.last_seen
            handle.inquiry_id = saved.id
            if self._postgres_handles:
                await self._handles.put(handle)
            else:
                self._handles.put(handle)
        self._cache[session.id] = session
        if self._memory_repo is not None:
            self._file(session.id).save(session.to_json())

    # ---- lifecycle ------------------------------------------------------------

    async def create(
        self,
        *,
        draft: InquiryDraft | None = None,
        mode: str = "intake",
        case_id: str | None = None,
        channel: str = "self_service",
        created_by: str | None = None,
        tenant_id: str | None = None,
        staff_id: str | None = None,
    ) -> Session:
        from app.store.session_bridge import session_from_parts

        inquiry = await self._repo.create(
            channel=channel,
            created_by=created_by,
            tenant_id=tenant_id,
            staff_id=staff_id,
            mode=mode,
            case_id=case_id,
        )
        if draft is not None:
            inquiry.draft = draft
            inquiry = await self._repo.save(inquiry)
        hid = str(inquiry.id)
        if self._postgres_handles:
            handle = await self._handles.create(inquiry_id=inquiry.id, handle_id=hid)
        else:
            handle = self._handles.create(inquiry_id=inquiry.id, handle_id=hid)
        handle.state.mode = mode
        if created_by is not None:
            handle.state.created_by = created_by
        session = session_from_parts(
            handle_id=handle.id,
            inquiry=inquiry,
            handle=handle.state,
            last_seen=handle.last_seen_at,
            created_at=handle.created_at,
        )
        async with self._meta_lock:
            self._register(session)
        return session

    async def get(self, session_id: str) -> Session:
        lock = await self._lock_for(session_id)
        async with lock:
            session = self._cache.get(session_id)
            if session is None:
                session = await self._load_session(session_id)
                self._cache[session_id] = session
            if self._is_expired(session):
                self._forget(session_id)
                raise SessionNotFound(session_id)
            return session

    def _is_expired_at(self, last_seen: datetime) -> bool:
        return datetime.now(tz=UTC) - last_seen > self._ttl

    async def touch(self, session_id: str) -> Session:
        from app.store.session_bridge import inquiry_id_for

        session = await self.get(session_id)
        now = datetime.now(tz=UTC)
        touched = await self._repo.touch(inquiry_id_for(session), now=now)
        session.last_seen = touched.last_seen_at
        session._version = touched.version
        if self._postgres_handles:
            handle = await self._handles.get(session_id)
        else:
            handle = self._handles.get(session_id)
        if handle is not None:
            handle.last_seen_at = touched.last_seen_at
            if self._postgres_handles:
                await self._handles.put(handle)
            else:
                self._handles.put(handle)
        return session

    async def revive(self, session_id: str) -> Session:
        if not _SAFE_ID.match(session_id):
            raise SessionNotFound(session_id)
        async with self._meta_lock:
            session = self._cache.get(session_id)
            if session is None:
                if self._memory_repo is not None:
                    raw = self._file(session_id).load(None)
                    if raw is not None:
                        from app.store.session_bridge import (
                            handle_from_session,
                            legacy_inquiry_from_session,
                        )

                        session = Session.from_json(raw)
                        inquiry = legacy_inquiry_from_session(session)
                        self._memory_repo.bootstrap(inquiry)
                        self._handles.put(
                            self._HandleRecord(
                                id=session.id,
                                inquiry_id=inquiry.id,
                                created_at=session.created_at,
                                last_seen_at=session.last_seen,
                                state=handle_from_session(session),
                            )
                        )
                        self._register(session)
                if session is None:
                    try:
                        session = await self._load_session(session_id)
                        self._register(session)
                    except SessionNotFound:
                        raise
        session.last_seen = datetime.now(tz=UTC)
        await self.touch(session_id)
        return session

    async def begin_turn(self, session_id: str) -> str:
        from app.store.errors import TurnInProgress as RepoTurnInProgress
        from app.store.session_bridge import inquiry_id_for

        session = await self.get(session_id)
        from app.config import get_settings

        lease_s = get_settings().turn_lease_seconds
        try:
            return await self._repo.acquire_turn(inquiry_id_for(session), lease_s)
        except RepoTurnInProgress as exc:
            raise TurnInProgress from exc

    async def begin_turn_waiting(self, session_id: str, wait_s: float) -> str:
        """`begin_turn`, waiting up to `wait_s` for a turn already running to finish.

        For a card action that doesn't run the agent itself, such as a document upload: the
        user can pick a file while the agent is still replying, and the upload should land
        once that reply ends rather than fail with 409 `turn_in_progress`.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(wait_s, 0.0)
        while True:
            try:
                return await self.begin_turn(session_id)
            except TurnInProgress:
                if loop.time() >= deadline:
                    raise
                await asyncio.sleep(0.2)

    async def end_turn(self, session_id: str, lease_id: str) -> None:
        from app.store.session_bridge import inquiry_id_for

        session = await self.get(session_id)
        await self._repo.release_turn(inquiry_id_for(session), lease_id)

    async def renew_turn(self, session_id: str, lease_id: str) -> None:
        from app.config import get_settings
        from app.store.session_bridge import inquiry_id_for

        session = await self.get(session_id)
        await self._repo.renew_turn(
            inquiry_id_for(session),
            lease_id,
            get_settings().turn_lease_seconds,
        )

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._meta_lock:
            if session_id not in self._locks:
                if self._postgres_handles or self._handles.get(session_id) is not None:
                    self._locks[session_id] = asyncio.Lock()
                    self._turn_locks[session_id] = asyncio.Lock()
                else:
                    raise SessionNotFound(session_id)
            return self._locks[session_id]

    def _forget(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
        self._locks.pop(session_id, None)
        self._turn_locks.pop(session_id, None)

    def _is_expired(self, session: Session) -> bool:
        return datetime.now(tz=UTC) - session.last_seen > self._ttl
