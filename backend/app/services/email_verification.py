"""Email verification by one-time link (mock).

The requirements verify the email by a link sent to the inbox (§7.1.1). The POC
mocks the inbox: `send_link` issues a single-use token and logs that a link was
sent (never the token). In demo mode the verification card exposes the token so a
"Verify email" button can stand in for clicking the link.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailLinkCheck:
    """Outcome of following a link: the address it was issued for, if the token was valid."""

    verified_email: str | None


class EmailVerificationService(Protocol):
    async def send_link(self, session_id: str, email: str) -> None: ...

    async def verify(self, session_id: str, token: str) -> EmailLinkCheck: ...

    def demo_token(self, session_id: str) -> str | None: ...


class MockEmailVerificationService:
    def __init__(self) -> None:
        # One live token per session; a new link replaces the old one.
        self._tokens: dict[str, tuple[str, str]] = {}
        self._send_count: dict[str, int] = {}

    def send_count(self, session_id: str) -> int:
        return self._send_count.get(session_id, 0)

    async def send_link(self, session_id: str, email: str) -> None:
        self._tokens[session_id] = (secrets.token_urlsafe(16), email)
        self._send_count[session_id] = self._send_count.get(session_id, 0) + 1
        logger.info("Email verification link sent for session %s", session_id)

    async def verify(self, session_id: str, token: str) -> EmailLinkCheck:
        issued = self._tokens.get(session_id)
        if issued is None or not secrets.compare_digest(issued[0], token):
            return EmailLinkCheck(verified_email=None)
        del self._tokens[session_id]
        return EmailLinkCheck(verified_email=issued[1])

    def demo_token(self, session_id: str) -> str | None:
        issued = self._tokens.get(session_id)
        return issued[0] if issued else None
