"""Email verification by one-time link (simulated email system, L3 §3.2).

`send_link` issues a signed `verify_email` token (purpose, inquiry id, a fingerprint of
the address, a nonce, an expiry) and emails `<PUBLIC_BASE_URL>/inquiry/verify?t=<token>`
through the notification service, so the message lands in the dev inbox. Only the latest
link for an inquiry works, and only once (its nonce is consumed). The token is never
logged. In demo mode (`EMAIL_LINK_DEMO`) the verification card carries the token so a
button can stand in for clicking the link.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.notifications import NotificationService
from app.persistence import JsonFile, data_path
from app.security import tokens

logger = logging.getLogger(__name__)

LinkError = Literal["token_invalid", "token_expired", "token_used"]


@dataclass(frozen=True)
class EmailLinkCheck:
    """Outcome of following a link: the address it was issued for, if the token was valid."""

    verified_email: str | None
    session_id: str | None = None
    error: LinkError | None = None


class EmailVerificationService(Protocol):
    async def send_link(
        self, session_id: str, email: str, context: dict[str, Any] | None = None
    ) -> None: ...

    async def verify(self, session_id: str, token: str) -> EmailLinkCheck: ...

    async def verify_link(self, token: str) -> EmailLinkCheck: ...

    def demo_token(self, session_id: str) -> str | None: ...


class MockEmailVerificationService:
    def __init__(
        self,
        *,
        secret: str = "dev-only-change-me",
        notifications: NotificationService | None = None,
        public_base_url: str = "http://localhost:5173",
        ttl_hours: int = 72,
        data_dir: str | None = None,
    ) -> None:
        self._secret = secret
        self._notifications = notifications
        self._base = public_base_url.rstrip("/")
        self._ttl_hours = ttl_hours
        self._file = JsonFile(data_path(data_dir, "mock_world", "email_links.json"))
        state = self._file.load({})
        # One live link per inquiry: {session_id: {"token", "nonce", "email"}}.
        self._links: dict[str, dict[str, str]] = dict(state.get("links", {}))
        self._send_count: dict[str, int] = dict(state.get("send_count", {}))

    def _save(self) -> None:
        self._file.save({"links": self._links, "send_count": self._send_count})

    def send_count(self, session_id: str) -> int:
        return self._send_count.get(session_id, 0)

    async def send_link(
        self, session_id: str, email: str, context: dict[str, Any] | None = None
    ) -> None:
        token, claims = tokens.issue(
            self._secret,
            "verify_email",
            session_id,
            ttl_seconds=self._ttl_hours * 3600,
            data={"e": tokens.fingerprint(email)},
        )
        self._links[session_id] = {"token": token, "nonce": claims.nonce, "email": email}
        self._send_count[session_id] = self._send_count.get(session_id, 0) + 1
        self._save()
        if self._notifications is not None:
            await self._notifications.send(
                "email_verification_link",
                email,
                {
                    **(context or {}),
                    "verify_url": f"{self._base}/inquiry/verify?t={token}",
                    "ttl_hours": self._ttl_hours,
                },
                inquiry_id=session_id,
            )
        logger.info("Email verification link sent for session %s", session_id)

    async def verify_link(self, token: str) -> EmailLinkCheck:
        """Check and consume a link token without knowing the session in advance."""
        try:
            claims = tokens.read(self._secret, token, "verify_email")
        except tokens.TokenError as exc:
            return EmailLinkCheck(verified_email=None, error=exc.code)
        issued = self._links.get(claims.subject)
        if issued is None or issued["nonce"] != claims.nonce:
            return EmailLinkCheck(
                verified_email=None, session_id=claims.subject, error="token_used"
            )
        del self._links[claims.subject]
        self._save()
        return EmailLinkCheck(verified_email=issued["email"], session_id=claims.subject)

    async def verify(self, session_id: str, token: str) -> EmailLinkCheck:
        try:
            claims = tokens.read(self._secret, token, "verify_email")
        except tokens.TokenError as exc:
            return EmailLinkCheck(verified_email=None, error=exc.code)
        if claims.subject != session_id:
            return EmailLinkCheck(verified_email=None, error="token_invalid")
        return await self.verify_link(token)

    def demo_token(self, session_id: str) -> str | None:
        issued = self._links.get(session_id)
        return issued["token"] if issued else None
