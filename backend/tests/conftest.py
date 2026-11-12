from pathlib import Path

import pytest
from app.policy.config import PolicyConfig, get_policy, use_policy

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
    "flow": ["unit"],
    "gateway": ["contract"],
    "handoff": ["agent"],
    "lifecycle": ["api"],
    "policy": ["unit"],
    "proactive": ["unit"],
    "scenarios": ["agent"],
    "parity": ["parity", "agent"],
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
def _restore_policy(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Each test starts with the active policy and can't leak a swapped one into the next.

    Tests written before the Lease Admin level (demo feedback §3.2, day R1) run with one
    reviewer role doing both levels (`first_level_review_role: null`), as they were
    written; tests marked `lease_admin` run with the shipped policy (Lease Admin first).
    Likewise tests written for the CR lookup run with `public_cr_check: lookup` unless
    marked `cr_question`, and tests written before per-document and per-contact approval
    (demo feedback §3.4, §3.5, day R2) run without it unless marked `approvals`.
    `create_app` installs the policy file it loads, so the loader it calls is wrapped too.
    """
    overrides: dict[str, object] = {}
    if request.node.get_closest_marker("lease_admin") is None:
        overrides["first_level_review_role"] = None
    if request.node.get_closest_marker("cr_question") is None:
        # Demo feedback §3.1: tests written for the CR lookup keep it after the policy
        # flips to `ask_then_sign_in`; tests marked `cr_question` run with the shipped one.
        overrides["public_cr_check"] = "lookup"
    if request.node.get_closest_marker("approvals") is None:
        overrides["document_approval"] = False
        overrides["contacts"] = {
            "approval_required": False,
            "ask_signatory": False,
            "applicant_signatory_needs_approval": False,
        }
    if request.node.get_closest_marker("lead_approval") is None:
        # Flow v2 §3.7 (day F2): tests written for one final approval after the contacts
        # (contacts opening at first approval, per-contact approval under `approvals`) keep
        # that flow; tests marked `lead_approval` run with the shipped second level.
        overrides["lead_approval"] = {"enabled": False, "require_unit_assigned": False}
        overrides["auto_request_contacts_after_first_approval"] = True
        if request.node.get_closest_marker("approvals") is not None:
            contacts = get_policy().contacts.model_dump(mode="json")
            overrides["contacts"] = {**contacts, "approval_required": True}
    if request.node.get_closest_marker("intake_v2") is not None:
        # Flow v2 §3.3 (day F3): new self-service inquiries run the v2 public intake. Off in
        # the shipped policy until the F3 Cursor PR flips it with the prompt and cards.
        intake = get_policy().flow_v2_intake.model_dump(mode="json")
        overrides["flow_v2_intake"] = {**intake, "enabled": True}
    policy = get_policy()
    if overrides:
        policy = policy.with_changes(**overrides)
        import app.main as main_module

        real_load = main_module.load_policy

        def _written_for(path: str | Path | None = None) -> PolicyConfig:
            return real_load(path).with_changes(**overrides)

        monkeypatch.setattr(main_module, "load_policy", _written_for)
    with use_policy(policy):
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
