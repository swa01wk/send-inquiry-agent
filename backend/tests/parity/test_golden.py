"""Replay parity scripts and compare to golden JSONL transcripts."""

from __future__ import annotations

import pytest
from app.config import Settings

from tests.parity.compare import compare_streams
from tests.parity.normalize import events_from_jsonl, split_turns
from tests.parity.recorder import golden_path, record_scenario
from tests.parity.scenarios import all_scenarios


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
    turns = split_turns(events)

    # Turn index after user script: message, confirm, message, confirm, verify_email,
    # wrong×2, wrong×3 (agent), correct otp, documents_updated.
    quiet_turn_indices = {4, 5, 6}  # verify_email, wrong, wrong
    for idx in quiet_turn_indices:
        assert idx < len(turns), f"expected at least {idx + 1} turns"
        types = [item["event"] for item in turns[idx]]
        assert "token" not in types, f"turn {idx} should be quiet, got {types}"

    # Third wrong code runs an agent turn (otp_resent).
    assert "token" in [item["event"] for item in turns[7]]
