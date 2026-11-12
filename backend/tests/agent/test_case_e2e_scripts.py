"""E2e script name resolution."""

from app.agent.e2e_scripts import resolve_e2e_scenario


def test_resolve_e2e_scenario_accepts_known_script() -> None:
    assert resolve_e2e_scenario("t2-reupload") == "t2-reupload"
    assert resolve_e2e_scenario("t1-contacts") == "t1-contacts"
    assert resolve_e2e_scenario("flow-v2-s19") == "flow-v2-s19"
    assert resolve_e2e_scenario("flow-v2-s20") == "flow-v2-s20"
    assert resolve_e2e_scenario("flow-v2-s21") == "flow-v2-s21"
    assert resolve_e2e_scenario("flow-v2-s22") == "flow-v2-s22"
    assert resolve_e2e_scenario("flow-v2-s23") == "flow-v2-s23"
    assert resolve_e2e_scenario("flow-v2-s24") == "flow-v2-s24"


def test_resolve_e2e_scenario_rejects_unknown_or_blank() -> None:
    assert resolve_e2e_scenario(None) is None
    assert resolve_e2e_scenario("  ") is None
    assert resolve_e2e_scenario("not-a-real-script") is None
