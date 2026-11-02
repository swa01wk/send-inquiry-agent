#!/usr/bin/env -S uv run python
"""Export frontend mock scenarios from parity golden JSONL files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.parity.normalize import events_from_jsonl, split_turns
from tests.parity.recorder import golden_path, session_sidecar_path
from tests.parity.scenarios import ParityScenario, ScriptStep, all_scenarios

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FE_DIR = _REPO_ROOT / "frontend" / "src" / "mocks" / "scenarios" / "parity"


def _when_for_step(step: ScriptStep) -> dict[str, Any]:
    if step.kind == "message":
        return {"type": "message", "textEquals": step.text}
    if step.kind == "confirm_latest":
        return {"type": "action", "action": "confirm_card"}
    if step.kind == "verify_email":
        return {"type": "action", "action": "verify_email"}
    if step.kind == "submit_otp":
        return {"type": "action", "action": "submit_otp"}
    if step.kind == "action":
        return {"type": "action", "action": step.action}
    if step.kind == "upload":
        return {"type": "any"}
    msg = f"no FE mapping for step kind {step.kind}"
    raise ValueError(msg)


def _chat_steps(script: list[ScriptStep]) -> list[ScriptStep]:
    """Steps that hit /chat (uploads only change server state before documents_updated)."""
    return [step for step in script if step.kind != "upload"]


def _load_initial_session(name: str) -> dict[str, Any]:
    path = session_sidecar_path(name)
    if not path.is_file():
        msg = f"missing {path}; run `make golden`"
        raise FileNotFoundError(msg)
    session = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    session["session_id"] = "mock-session"
    return session


def export_scenario(scenario: ParityScenario) -> dict[str, Any]:
    path = golden_path(scenario.name)
    if not path.is_file():
        msg = f"missing golden {path}; run `make golden` first"
        raise FileNotFoundError(msg)
    events = events_from_jsonl(path.read_text(encoding="utf-8"))
    turns = split_turns(events)
    chat_steps = _chat_steps(scenario.script)

    if len(turns) != len(chat_steps):
        msg = (
            f"{scenario.name}: {len(turns)} SSE turns vs {len(chat_steps)} chat steps; "
            "adjust the script or golden"
        )
        raise ValueError(msg)

    fe_turns: list[dict[str, Any]] = []
    accumulated: list[dict[str, Any]] = []
    for step, turn_events in zip(chat_steps, turns, strict=True):
        if step.kind == "upload":
            continue
        when = _when_for_step(step)
        sse = [{"event": item["event"], "data": item["data"]} for item in turn_events]
        fe_turns.append({"when": when, "events": sse})
        accumulated.extend(turn_events)

    return {
        "name": scenario.name,
        "session": _load_initial_session(scenario.name),
        "turns": fe_turns,
    }


def main() -> None:
    _FE_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in all_scenarios():
        payload = export_scenario(scenario)
        out = _FE_DIR / f"{scenario.name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(_REPO_ROOT)}")


if __name__ == "__main__":
    main()
