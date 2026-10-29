"""The app's clock (L5 §3.1): system time, or simulated time for demos and tests.

Everything that stamps a business record (case transitions, requests, document uploads,
invitations, audit events, notifications) reads `now()`, so moving a `SimulatedClock`
forward makes cases look older without touching any record. Session idle timeouts and
signed-link expiry keep real time: they protect the applicant, not the demo.

`build_services` installs `SimulatedClock` when DEV_TOOLS is on (moved by
`POST /api/dev/clock/advance`), and `SystemClock` otherwise.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    simulated = False

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class SimulatedClock:
    """Real time plus an offset that only moves forward. `base` freezes time (tests)."""

    simulated = True

    def __init__(self, base: datetime | None = None) -> None:
        self._base = base
        self._offset = timedelta(0)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        start = self._base if self._base is not None else datetime.now(tz=UTC)
        with self._lock:
            return start + self._offset

    @property
    def offset(self) -> timedelta:
        with self._lock:
            return self._offset

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            msg = "the simulated clock only moves forward"
            raise ValueError(msg)
        with self._lock:
            self._offset += delta
        return self.now()

    def freeze(self, at: datetime) -> None:
        """Stop real time at `at` (tests and scripted demos); the offset still applies."""
        with self._lock:
            self._base = at

    def reset(self) -> None:
        with self._lock:
            self._offset = timedelta(0)


_clock: Clock = SystemClock()


def install_clock(clock: Clock) -> None:
    global _clock
    _clock = clock


def get_clock() -> Clock:
    return _clock


def now() -> datetime:
    return _clock.now()
