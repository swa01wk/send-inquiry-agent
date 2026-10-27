"""Mobile one-time password (simulated SMS gateway, L3 §3.1).

The OTP verifies the mobile number only (requirements §7.1.1). Email is verified
separately by link; a landline never receives an OTP. The code (`OTP_MOCK_CODE`) is
delivered to the dev outbox as an SMS and never logged.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.notifications import NotificationService
from app.persistence import JsonFile, data_path

logger = logging.getLogger(__name__)


class OtpService(Protocol):
    async def send(
        self, session_id: str, mobile: str, context: dict[str, Any] | None = None
    ) -> None: ...

    async def verify(self, session_id: str, code: str) -> bool: ...


class MockOtpService:
    def __init__(
        self,
        mock_code: str,
        *,
        notifications: NotificationService | None = None,
        data_dir: str | None = None,
    ) -> None:
        self._mock_code = mock_code
        self._notifications = notifications
        self._file = JsonFile(data_path(data_dir, "mock_world", "otp.json"))
        state = self._file.load({})
        self._active_sessions: set[str] = set(state.get("active", []))
        self._send_count: dict[str, int] = dict(state.get("send_count", {}))

    def _save(self) -> None:
        self._file.save({"active": sorted(self._active_sessions), "send_count": self._send_count})

    def send_count(self, session_id: str) -> int:
        return self._send_count.get(session_id, 0)

    async def send(
        self, session_id: str, mobile: str, context: dict[str, Any] | None = None
    ) -> None:
        self._active_sessions.add(session_id)
        self._send_count[session_id] = self._send_count.get(session_id, 0) + 1
        self._save()
        if self._notifications is not None:
            await self._notifications.send(
                "sms_otp",
                mobile,
                {**(context or {}), "code": self._mock_code},
                inquiry_id=session_id,
            )
        logger.info("OTP sent for session %s", session_id)

    async def verify(self, session_id: str, code: str) -> bool:
        if session_id not in self._active_sessions:
            return False
        return code == self._mock_code
