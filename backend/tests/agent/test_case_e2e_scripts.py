"""E2e script name resolution."""

from app.agent.e2e_scripts import resolve_e2e_scenario


def test_resolve_e2e_scenario_accepts_known_script() -> None:
    assert resolve_e2e_scenario("t2-reupload") == "t2-reupload"
    assert resolve_e2e_scenario("t1-contacts") == "t1-contacts"


def test_resolve_e2e_scenario_rejects_unknown_or_blank() -> None:
    assert resolve_e2e_scenario(None) is None
    assert resolve_e2e_scenario("  ") is None
    assert resolve_e2e_scenario("not-a-real-script") is None
