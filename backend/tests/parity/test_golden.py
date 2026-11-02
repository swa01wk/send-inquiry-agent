"""Replay parity scripts and compare to golden JSONL transcripts."""

from __future__ import annotations

import pytest
from app.config import Settings

from tests.parity.compare import compare_streams
from tests.parity.normalize import chat_turns_for_script, events_from_jsonl
from tests.parity.recorder import golden_path, record_scenario
from tests.parity.scenarios import ScriptStep, all_scenarios


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario_name",
    [scenario.name for scenario in all_scenarios()],
)
async def test_golden_transcript(settings: Settings, scenario_name: str) -> None:
    path = golden_path(scenario_name)
    assert path.is_file(), f"missing golden {path}; run `make golden`"
    expected = events_from_jsonl(path.read_text(encoding="utf-8"))

    scenario = next(s for s in all_scenarios() if s.name == scenario_name)
    actual, _session = await record_scenario(settings, scenario)

    diffs = compare_streams(expected, actual)
    if diffs:
        joined = "\n".join(diffs)
        pytest.fail(f"golden mismatch for {scenario_name}:\n{joined}")


@pytest.mark.asyncio
async def test_quiet_actions_emit_no_tokens(settings: Settings) -> None:
    """Wrong OTP attempts 1–2 and verify_email while mobile pending are quiet (step 12)."""
    from tests.parity.scenarios import scenario_by_name

    scenario = scenario_by_name("wrong-otp-three-times")
    events, _session = await record_scenario(settings, scenario)
    paired = chat_turns_for_script(scenario.script, events)

    def turn_for(step: ScriptStep) -> list[dict]:
        for script_step, turn in paired:
            if script_step is step:
                return turn
        msg = f"no turn recorded for script step {step!r}"
        raise AssertionError(msg)

    verify_turn = turn_for(scenario.script[4])  # verify_email
    assert scenario.script[4].kind == "verify_email"
    assert "token" not in [item["event"] for item in verify_turn]

    wrong_steps = [
        step
        for step in scenario.script
        if step.kind == "action"
        and step.action == "submit_otp"
        and step.payload.get("code") == "0000"
    ]
    assert len(wrong_steps) == 3
    for step in wrong_steps[:2]:
        types = [item["event"] for item in turn_for(step)]
        assert "token" not in types, f"wrong OTP should be quiet, got {types}"

    third_wrong = wrong_steps[2]
    third_types = [item["event"] for item in turn_for(third_wrong)]
    assert "token" in third_types, f"third wrong OTP should run agent turn, got {third_types}"
