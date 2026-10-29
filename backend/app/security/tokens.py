"""Signed, single-purpose link tokens (L3 §3.2, §3.4).

Format: ``<base64url(json claims)>.<base64url(hmac-sha256)>``. Standard library only
(DELIVERY-PLAN §A5); the claims are signed, not encrypted, so they carry ids and a
nonce but never an email, phone number or code.

Purposes:
- ``verify_email``: the emailed verification link. Single use (the nonce is consumed).
- ``resume``: reopen an inquiry in the chat on any device.
- ``track``: the private tracking page for a submitted reference.
- ``case``: a request link after submission (re-upload, contacts, sales data); subject is
  the reference, ``data.r`` the request id (L4 §3.5, §3.9).
- ``complete``: the application link a call-centre executive sends (intake channels §3.2);
  subject is the staff session; the session keeps the current link's nonce, so a resend
  makes the old link stop working and the link is single use.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal

Purpose = Literal["verify_email", "resume", "track", "case", "complete"]


class TokenError(Exception):
    """A token that can't be used. `code` is safe to show to clients."""

    def __init__(self, code: Literal["token_invalid", "token_expired"]) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TokenClaims:
    purpose: Purpose
    subject: str  # inquiry id (session id), or the reference for `track`
    expires_at: int  # unix seconds
    nonce: str
    data: dict[str, Any]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def issue(
    secret: str,
    purpose: Purpose,
    subject: str,
    *,
    ttl_seconds: int,
    data: dict[str, Any] | None = None,
    now: float | None = None,
) -> tuple[str, TokenClaims]:
    """A new token and its claims (callers keep the nonce when it must be single-use)."""
    issued_at = int(now if now is not None else time.time())
    claims = TokenClaims(
        purpose=purpose,
        subject=subject,
        expires_at=issued_at + ttl_seconds,
        nonce=secrets.token_urlsafe(12),
        data=dict(data or {}),
    )
    payload = {
        "p": claims.purpose,
        "s": claims.subject,
        "e": claims.expires_at,
        "n": claims.nonce,
        "d": claims.data,
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{body}.{_sign(secret, body)}", claims


def read(
    secret: str,
    token: str,
    purpose: Purpose,
    *,
    now: float | None = None,
) -> TokenClaims:
    """Verify signature, purpose and expiry. Raises TokenError."""
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("token_invalid") from exc
    if not hmac.compare_digest(_sign(secret, body), signature):
        raise TokenError("token_invalid")
    try:
        payload = json.loads(_unb64(body))
        claims = TokenClaims(
            purpose=payload["p"],
            subject=str(payload["s"]),
            expires_at=int(payload["e"]),
            nonce=str(payload["n"]),
            data=dict(payload.get("d") or {}),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenError("token_invalid") from exc
    if claims.purpose != purpose:
        raise TokenError("token_invalid")
    current = int(now if now is not None else time.time())
    if current >= claims.expires_at:
        raise TokenError("token_expired")
    return claims


def fingerprint(value: str) -> str:
    """Short, non-reversible tag for a value (e.g. the email a link was sent to)."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]
