import pytest
from app.policy.config import get_policy, use_policy

pytest_plugins = ["tests.api.conftest"]


@pytest.fixture(autouse=True)
def _restore_policy():
    """Each test starts with the active policy and can't leak a swapped one into the next."""
    with use_policy(get_policy()):
        yield
