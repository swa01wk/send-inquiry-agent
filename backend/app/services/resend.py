"""Resend limits for the email link and the OTP (L3 §3.3).

Policy `resend.cooldown_seconds` between sends on a channel, and at most
`resend.max_per_hour` sends per channel per inquiry. The first send is never delayed.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.persistence import JsonFile, data_path
from app.policy.config import get_policy

Channel = Literal["email", "sms"]


class ResendLimiter:
    def __init__(
        self,
        data_dir: str | None = None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._file = JsonFile(data_path(data_dir, "mock_world", "sends.json"))
        self._sends: dict[str, dict[str, list[str]]] = dict(self._file.load({}))
        self._clock = clock
        self._lock = threading.Lock()

    def _times(self, inquiry_id: str, channel: Channel) -> list[datetime]:
        raw = self._sends.get(inquiry_id, {}).get(channel, [])
        return [datetime.fromisoformat(t) for t in raw]

    def available_at(self, inquiry_id: str, channel: Channel) -> datetime | None:
        """When the next send on this channel is allowed; None if it is allowed now."""
        policy = get_policy().resend
        now = self._clock()
        times = self._times(inquiry_id, channel)
        if not times:
            return None
        candidates = [times[-1] + timedelta(seconds=policy.cooldown_seconds)]
        recent = [t for t in times if now - t < timedelta(hours=1)]
        if len(recent) >= policy.max_per_hour:
            candidates.append(recent[-policy.max_per_hour] + timedelta(hours=1))
        ready = max(candidates)
        return ready if ready > now else None

    def wait_seconds(self, inquiry_id: str, channel: Channel) -> int:
        ready = self.available_at(inquiry_id, channel)
        if ready is None:
            return 0
        return max(1, int((ready - self._clock()).total_seconds() + 0.999))

    def record(self, inquiry_id: str, channel: Channel) -> None:
        with self._lock:
            entry = self._sends.setdefault(inquiry_id, {})
            history = entry.setdefault(channel, [])
            history.append(self._clock().isoformat())
            cutoff = self._clock() - timedelta(hours=1)
            entry[channel] = [t for t in history if datetime.fromisoformat(t) >= cutoff]
            self._file.save(self._sends)
