"""The thin gateway around every external call (M0 §7.1, Day 2 depth).

Every call to a simulated Cenomi system goes through `Gateway.call` (async) or
`Gateway.call_sync`. It gives:
- a timeout per service (async calls);
- one error taxonomy: failures become `GatewayError(kind)` with kind
  `timeout`, `unavailable`, `rejected` or `invalid`;
- fault injection for mocks (`MOCK_FAULTS`, or `X-Mock-Faults` per session in scripted
  mode), raised exactly like a real outage would be;
- an audit record of each call (`tool_called`, layer `service`) with its outcome and latency.

Retries, reconciliation and latency budgets arrive in step 14 (Sprint 1).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, cast

from app.audit import AuditLog
from app.services.errors import ServiceRejected, ServiceTimeout, ServiceUnavailable

ErrorKind = Literal["timeout", "unavailable", "rejected", "invalid"]
FaultKind = Literal["timeout", "unavailable", "rejected"]
SERVICES = (
    "cr",
    "email",
    "otp",
    "notifications",
    "submit",
    "status",
    "storage",
    "call_centre",
)

DEFAULT_TIMEOUTS_S: dict[str, float] = {
    "cr": 5.0,
    "email": 5.0,
    "otp": 5.0,
    "notifications": 5.0,
    "submit": 10.0,
    "status": 5.0,
    "storage": 10.0,
    "call_centre": 5.0,
}

T = TypeVar("T")


class GatewayError(Exception):
    def __init__(self, kind: ErrorKind, service: str, operation: str) -> None:
        super().__init__(f"{service}.{operation}: {kind}")
        self.kind: ErrorKind = kind
        self.service = service
        self.operation = operation

    @property
    def note(self) -> str:
        """The `[ui_event]`/tool-result token for the agent: `service_error <service> <kind>`."""
        return f"service_error {self.service} {self.kind}"


class FaultSpecError(ValueError):
    pass


@dataclass
class _Fault:
    kind: FaultKind
    remaining: int | None  # None = every call


@dataclass
class FaultPlan:
    """Parsed `service:kind[:count],…`. Count defaults to every call."""

    faults: dict[str, list[_Fault]] = field(default_factory=dict)

    @classmethod
    def parse(cls, spec: str | None) -> FaultPlan:
        plan = cls()
        for raw in (spec or "").split(","):
            item = raw.strip()
            if not item:
                continue
            parts = item.split(":")
            if len(parts) not in (2, 3):
                raise FaultSpecError(f"bad fault {item!r}: use service:kind[:count]")
            service, kind = parts[0].strip(), parts[1].strip()
            if service not in SERVICES:
                raise FaultSpecError(f"unknown service {service!r} in fault {item!r}")
            if kind not in ("timeout", "unavailable", "rejected"):
                raise FaultSpecError(f"unknown fault kind {kind!r} in fault {item!r}")
            count: int | None = None
            if len(parts) == 3:
                try:
                    count = int(parts[2])
                except ValueError as exc:
                    raise FaultSpecError(f"bad count in fault {item!r}") from exc
                if count < 1:
                    raise FaultSpecError(f"count must be at least 1 in fault {item!r}")
            plan.faults.setdefault(service, []).append(
                _Fault(kind=cast(FaultKind, kind), remaining=count)
            )
        return plan

    def take(self, service: str) -> FaultKind | None:
        for fault in self.faults.get(service, []):
            if fault.remaining is None:
                return fault.kind
            if fault.remaining > 0:
                fault.remaining -= 1
                return fault.kind
        return None


def _raise_fault(kind: FaultKind) -> None:
    if kind == "timeout":
        raise ServiceTimeout("injected timeout")
    if kind == "unavailable":
        raise ServiceUnavailable("injected outage")
    raise ServiceRejected("injected rejection")


def _classify(exc: BaseException) -> ErrorKind | None:
    if isinstance(exc, ServiceTimeout | TimeoutError | asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, ServiceUnavailable | ConnectionError):
        return "unavailable"
    if isinstance(exc, ServiceRejected):
        return "rejected"
    if isinstance(exc, ValueError):
        return "invalid"
    return None  # business outcomes and bugs propagate unchanged


class Gateway:
    def __init__(
        self,
        *,
        faults: FaultPlan | None = None,
        audit: AuditLog | None = None,
        timeouts_s: dict[str, float] | None = None,
        inject_faults: bool = True,
    ) -> None:
        self._global_faults = faults or FaultPlan()
        self._session_faults: dict[str, FaultPlan] = {}
        self._audit = audit
        self._timeouts = {**DEFAULT_TIMEOUTS_S, **(timeouts_s or {})}
        self._inject = inject_faults

    def set_session_faults(self, inquiry_id: str, spec: str | None) -> None:
        """Faults for one session (`X-Mock-Faults`, scripted mode only)."""
        if spec:
            self._session_faults[inquiry_id] = FaultPlan.parse(spec)

    def _injected(self, service: str, inquiry_id: str | None) -> FaultKind | None:
        if not self._inject:
            return None
        if inquiry_id is not None and inquiry_id in self._session_faults:
            kind = self._session_faults[inquiry_id].take(service)
            if kind is not None:
                return kind
        return self._global_faults.take(service)

    def _record(
        self,
        inquiry_id: str | None,
        service: str,
        operation: str,
        outcome: str,
        started: float,
    ) -> None:
        if self._audit is None or inquiry_id is None:
            return
        self._audit.record(
            inquiry_id,
            "tool_called",
            actor="system",
            payload={
                "layer": "service",
                "name": f"{service}.{operation}",
                "outcome": outcome,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    async def call(
        self,
        service: str,
        operation: str,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        inquiry_id: str | None = None,
        **kwargs: Any,
    ) -> T:
        started = time.perf_counter()
        try:
            fault = self._injected(service, inquiry_id)
            if fault is not None:
                _raise_fault(fault)
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=self._timeouts[service])
        except Exception as exc:
            kind = _classify(exc)
            if kind is None:
                self._record(inquiry_id, service, operation, "error", started)
                raise
            self._record(inquiry_id, service, operation, kind, started)
            raise GatewayError(kind, service, operation) from exc
        self._record(inquiry_id, service, operation, "ok", started)
        return result

    def call_sync(
        self,
        service: str,
        operation: str,
        fn: Callable[..., T],
        *args: Any,
        inquiry_id: str | None = None,
        **kwargs: Any,
    ) -> T:
        """For synchronous services. No timeout enforcement (mocks answer instantly)."""
        started = time.perf_counter()
        try:
            fault = self._injected(service, inquiry_id)
            if fault is not None:
                _raise_fault(fault)
            result = fn(*args, **kwargs)
        except Exception as exc:
            kind = _classify(exc)
            if kind is None:
                self._record(inquiry_id, service, operation, "error", started)
                raise
            self._record(inquiry_id, service, operation, kind, started)
            raise GatewayError(kind, service, operation) from exc
        self._record(inquiry_id, service, operation, "ok", started)
        return result
