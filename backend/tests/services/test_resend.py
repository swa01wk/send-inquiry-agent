from datetime import UTC, datetime, timedelta

from app.policy.config import load_policy, use_policy
from app.services.resend import ResendLimiter


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def test_first_send_is_free_then_cooldown_applies() -> None:
    clock = Clock()
    limiter = ResendLimiter(clock=clock)
    assert limiter.wait_seconds("s1", "email") == 0
    limiter.record("s1", "email")
    assert limiter.wait_seconds("s1", "email") == 60
    assert limiter.available_at("s1", "email") == clock.now + timedelta(seconds=60)
    clock.now += timedelta(seconds=60)
    assert limiter.wait_seconds("s1", "email") == 0
    assert limiter.wait_seconds("s1", "sms") == 0  # per channel


def test_hourly_cap() -> None:
    clock = Clock()
    limiter = ResendLimiter(clock=clock)
    for _ in range(5):
        limiter.record("s1", "sms")
        clock.now += timedelta(seconds=61)
    first = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
    assert limiter.available_at("s1", "sms") == first + timedelta(hours=1)


def test_limits_come_from_the_policy() -> None:
    clock = Clock()
    policy = load_policy().with_changes(resend={"cooldown_seconds": 10, "max_per_hour": 5})
    with use_policy(policy):
        limiter = ResendLimiter(clock=clock)
        limiter.record("s1", "email")
        assert limiter.wait_seconds("s1", "email") == 10


def test_history_survives_restart(tmp_path) -> None:
    clock = Clock()
    ResendLimiter(str(tmp_path), clock=clock).record("s1", "email")
    assert ResendLimiter(str(tmp_path), clock=clock).wait_seconds("s1", "email") == 60
