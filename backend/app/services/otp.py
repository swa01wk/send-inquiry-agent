"""Mobile one-time password mock service.

The OTP verifies the mobile number only (requirements §7.1.1). Email is verified
separately by link (see email_verification.py); a landline never receives an OTP.
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class OtpService(Protocol):
    async def send(self, session_id: str, mobile: str) -> None: ...

    async def verify(self, session_id: str, code: str) -> bool: ...


class MockOtpService:
    def __init__(self, mock_code: str) -> None:
        self._mock_code = mock_code
        self._active_sessions: set[str] = set()
        self._send_count: dict[str, int] = {}

    def send_count(self, session_id: str) -> int:
        return self._send_count.get(session_id, 0)

    async def send(self, session_id: str, mobile: str) -> None:
        del mobile
        self._active_sessions.add(session_id)
        self._send_count[session_id] = self._send_count.get(session_id, 0) + 1
        logger.info("OTP sent for session %s", session_id)

    async def verify(self, session_id: str, code: str) -> bool:
        if session_id not in self._active_sessions:
            return False
        return code == self._mock_code
