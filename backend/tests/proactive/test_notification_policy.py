"""NotificationPolicy (L5 §3.3): tiers, quiet hours across midnight, the per-case throttle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.policy.config import ProactivePolicy, QuietHours
from app.proactive.notification_policy import NotificationPolicy, in_quiet_hours, quiet_hours_end

POLICY = ProactivePolicy()  # 22:00–08:00 Asia/Riyadh (UTC+3), 48 h between messages


def riyadh(hour: int, minute: int = 0, day: int = 30) -> datetime:
    """A Riyadh wall-clock time as UTC (Riyadh is UTC+3, no daylight saving)."""
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC) - timedelta(hours=3)


def test_quiet_hours_cross_midnight() -> None:
    assert in_quiet_hours(riyadh(22, 0), POLICY)
    assert in_quiet_hours(riyadh(23, 0), POLICY)
    assert in_quiet_hours(riyadh(2, 30), POLICY)
    assert in_quiet_hours(riyadh(7, 59), POLICY)
    assert not in_quiet_hours(riyadh(8, 0), POLICY)
    assert not in_quiet_hours(riyadh(21, 59), POLICY)


def test_quiet_hours_end_is_next_morning() -> None:
    assert quiet_hours_end(riyadh(23, 0), POLICY) == riyadh(8, 0, day=31)
    assert quiet_hours_end(riyadh(3, 0), POLICY) == riyadh(8, 0)


def test_same_day_window() -> None:
    lunch = ProactivePolicy(quiet_hours=QuietHours(start="13:00", end="15:00"))
    assert in_quiet_hours(riyadh(14, 0), lunch)
    assert not in_quiet_hours(riyadh(16, 0), lunch)


def test_tier_zero_always_sends_even_at_night() -> None:
    verdict = NotificationPolicy(POLICY).check(tier=0, now=riyadh(23, 0))
    assert verdict.decision == "send"


def test_tier_two_needs_approval() -> None:
    gate = NotificationPolicy(POLICY)
    assert gate.check(tier=2, now=riyadh(10, 0)).decision == "awaiting_approval"
    assert gate.check(tier=2, now=riyadh(10, 0), approved=True).decision == "send"


def test_approved_at_23_is_held_until_08() -> None:
    verdict = NotificationPolicy(POLICY).check(tier=2, now=riyadh(23, 0), approved=True)
    assert verdict.decision == "held_quiet_hours"
    assert verdict.send_after == riyadh(8, 0, day=31)


def test_throttle_one_message_per_48_hours() -> None:
    gate = NotificationPolicy(POLICY)
    last = riyadh(10, 0)
    verdict = gate.check(tier=1, now=last + timedelta(hours=24), last_applicant_message=last)
    assert verdict.decision == "throttled"
    assert verdict.send_after == last + timedelta(hours=48)
    later = gate.check(tier=1, now=last + timedelta(hours=49), last_applicant_message=last)
    assert later.decision == "send"


def test_throttle_release_moves_out_of_quiet_hours() -> None:
    last = riyadh(23, 30, day=28)  # allowed again at 23:30 on the 30th → 08:00 on the 31st
    verdict = NotificationPolicy(POLICY).check(
        tier=1, now=riyadh(12, 0, day=29), last_applicant_message=last
    )
    assert verdict.decision == "throttled"
    assert verdict.send_after == riyadh(8, 0, day=31)
