"""One-time password mock service."""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class OtpService(Protocol):
    async def send(self, session_id: str, email: str, phone: str) -> None: ...

    async def verify(self, session_id: str, code: str) -> bool: ...


class MockOtpService:
    def __init__(self, mock_code: str) -> None:
        self._mock_code = mock_code
        self._active_sessions: set[str] = set()

    async def send(self, session_id: str, email: str, phone: str) -> None:
        del email, phone
        self._active_sessions.add(session_id)
        logger.info("OTP sent for session %s", session_id)

    async def verify(self, session_id: str, code: str) -> bool:
        if session_id not in self._active_sessions:
            return False
        return code == self._mock_code
