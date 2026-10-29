"""`NotificationPolicy.check` (L5 §3.3): may this proactive message go now?

- Tier 0 (internal flags to staff): sends.
- Tier 1 (pre-approved applicant message) and approved tier 2: sends, unless quiet hours
  or the per-case throttle hold it until a later time.
- Tier 2 not yet approved: awaits a reviewer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.policy.config import ProactivePolicy

Decision = Literal["send", "awaiting_approval", "held_quiet_hours", "throttled"]


@dataclass(frozen=True)
class PolicyVerdict:
    decision: Decision
    send_after: datetime | None = None


def _hm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_quiet_hours(now: datetime, policy: ProactivePolicy) -> bool:
    quiet = policy.quiet_hours
    local = now.astimezone(ZoneInfo(quiet.timezone)).time()
    start, end = _hm(quiet.start), _hm(quiet.end)
    if start <= end:  # same-day window, e.g. 13:00–15:00
        return start <= local < end
    return local >= start or local < end  # across midnight, e.g. 22:00–08:00


def quiet_hours_end(now: datetime, policy: ProactivePolicy) -> datetime:
    """The next moment the quiet window closes (UTC-aware)."""
    zone = ZoneInfo(policy.quiet_hours.timezone)
    local = now.astimezone(zone)
    end = _hm(policy.quiet_hours.end)
    candidate = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(now.tzinfo)


class NotificationPolicy:
    def __init__(self, policy: ProactivePolicy) -> None:
        self._policy = policy

    def check(
        self,
        *,
        tier: int,
        now: datetime,
        approved: bool = False,
        last_applicant_message: datetime | None = None,
    ) -> PolicyVerdict:
        if tier == 0:
            return PolicyVerdict("send")
        if tier >= 2 and not approved:
            return PolicyVerdict("awaiting_approval")
        if last_applicant_message is not None:
            allowed = last_applicant_message + timedelta(
                hours=self._policy.tenant_proactive_min_hours
            )
            if now < allowed:
                return PolicyVerdict("throttled", send_after=self._outside_quiet(allowed))
        if in_quiet_hours(now, self._policy):
            return PolicyVerdict("held_quiet_hours", send_after=quiet_hours_end(now, self._policy))
        return PolicyVerdict("send")

    def _outside_quiet(self, moment: datetime) -> datetime:
        if in_quiet_hours(moment, self._policy):
            return quiet_hours_end(moment, self._policy)
        return moment
