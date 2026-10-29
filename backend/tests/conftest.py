from pathlib import Path

import pytest
from app.policy.config import get_policy, use_policy

pytest_plugins = ["tests.api.conftest"]

_TESTS_ROOT = Path(__file__).resolve().parent

# Directory → markers (testing-strategy §2.1). Applied in pytest_collection_modifyitems
# because pytestmark in nested conftest files does not tag collected tests.
_DIR_MARKERS: dict[str, list[str]] = {
    "agent": ["agent"],
    "api": ["api"],
    "arabic": ["agent"],
    "audit": ["unit"],
    "case_brief": ["unit"],
    "contacts": ["unit"],
    "domain": ["unit"],
    "gateway": ["contract"],
    "handoff": ["agent"],
    "lifecycle": ["api"],
    "policy": ["unit"],
    "proactive": ["unit"],
    "scenarios": ["agent"],
    "security": ["unit"],
    "services": ["unit", "contract"],
}

_ROOT_FILE_MARKERS: dict[str, list[str]] = {
    "test_e2e_scripts.py": ["agent"],
    "test_e2e_scripts_regenerate.py": ["agent"],
    "test_faq.py": ["unit"],
    "test_health.py": ["api"],
    "test_sessions.py": ["api"],
    "test_turn_log.py": ["unit"],
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        try:
            rel = item.path.relative_to(_TESTS_ROOT)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) == 1 and parts[0] in _ROOT_FILE_MARKERS:
            names = _ROOT_FILE_MARKERS[parts[0]]
        elif len(parts) >= 2 and parts[0] in _DIR_MARKERS:
            names = _DIR_MARKERS[parts[0]]
        else:
            continue
        for name in names:
            item.add_marker(getattr(pytest.mark, name))


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
