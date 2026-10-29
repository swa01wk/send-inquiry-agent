"""Azure AD, simulated (L4 §3.2, assumption A3).

`invite` records the tenant role the invitation assigns (requirements §7.12.2) and sends
an `azure_ad_invitation` message whose "Accept invitation" link
(`GET /api/dev/identity/accept/{id}`, dev tools) marks it accepted and creates the
account. `has_account` keeps anyone who already has an account from being invited.
"""

from __future__ import annotations

import functools
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Protocol

from app import clock
from app.notifications import MockNotificationService
from app.persistence import JsonFile, data_path
from app.workflow.models import Invitation

ACCOUNTS_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_world" / "identity.json"


class IdentityService(Protocol):
    async def invite(
        self, email: str, role: str, context: dict[str, Any], *, inquiry_id: str
    ) -> Invitation: ...

    def has_account(self, email: str) -> bool: ...

    def status(self, invitation_id: str) -> Invitation | None: ...

    def accept(self, invitation_id: str) -> Invitation | None: ...


class MockIdentityService:
    def __init__(
        self,
        *,
        notifications: MockNotificationService,
        public_api_url: str,
        data_dir: str | None = None,
    ) -> None:
        self._notifications = notifications
        self._api = public_api_url.rstrip("/")
        self._file = JsonFile(data_path(data_dir, "mock_world", "identity_state.json"))
        seeded = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))["accounts"]
        state = self._file.load({})
        self._accounts: set[str] = {a.lower() for a in [*seeded, *state.get("accounts", [])]}
        self._invitations: dict[str, dict[str, Any]] = dict(state.get("invitations", {}))
        self._lock = threading.Lock()

    def _save(self) -> None:
        self._file.save({"accounts": sorted(self._accounts), "invitations": self._invitations})

    def has_account(self, email: str) -> bool:
        return email.strip().lower() in self._accounts

    def status(self, invitation_id: str) -> Invitation | None:
        raw = self._invitations.get(invitation_id)
        if not raw:
            return None
        invitation: Invitation = Invitation.model_validate(raw)
        return invitation

    async def invite(
        self, email: str, role: str, context: dict[str, Any], *, inquiry_id: str
    ) -> Invitation:
        invitation = Invitation(
            id=f"inv_{uuid.uuid4().hex[:10]}",
            email=email,
            role=role,
            invited_at=clock.now(),
        )
        with self._lock:
            self._invitations[invitation.id] = invitation.model_dump(mode="json")
            self._save()
        send = functools.partial(self._notifications.send, inquiry_id=inquiry_id)
        await send(
            "azure_ad_invitation",
            email,
            {
                **context,
                "role_label": role.replace("_", " ").title(),
                "accept_url": f"{self._api}/api/dev/identity/accept/{invitation.id}",
            },
        )
        return invitation

    def accept(self, invitation_id: str) -> Invitation | None:
        with self._lock:
            raw = self._invitations.get(invitation_id)
            if raw is None:
                return None
            if raw.get("accepted_at") is None:
                raw["accepted_at"] = clock.now().isoformat()
            self._accounts.add(str(raw["email"]).lower())
            self._save()
            accepted: Invitation = Invitation.model_validate(raw)
            return accepted
