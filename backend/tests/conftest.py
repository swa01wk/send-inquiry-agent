import pytest
from app.policy.config import get_policy, use_policy

pytest_plugins = ["tests.api.conftest"]


@pytest.fixture(autouse=True)
def _restore_policy():
    """Each test starts with the active policy and can't leak a swapped one into the next."""
    with use_policy(get_policy()):
        yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The slowapi limiter is process-wide: each test starts with fresh counters, so many
    sessions created by earlier tests in the same minute can't 429 a later one."""
    from app.api.limiter import limiter

    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _real_clock():
    """Services built with DEV_TOOLS install a simulated clock; put real time back after."""
    from app.clock import SystemClock, install_clock

    yield
    install_clock(SystemClock())
