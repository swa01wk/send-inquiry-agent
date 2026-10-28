from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agent.case_tools import CASE_TOOLS
from app.agent.e2e_scripts import list_e2e_script_names, load_e2e_script_steps
from app.agent.tools import TOOLS

_TOOL_NAMES = {t.name for t in TOOLS} | {t.name for t in CASE_TOOLS}
_SCRIPTS_DIR = Path(__file__).resolve().parent / "e2e_scripts"


@pytest.mark.parametrize("name", list_e2e_script_names())
def test_e2e_script_parses_and_uses_known_tools(name: str) -> None:
    steps = load_e2e_script_steps(name)
    assert isinstance(steps, list)
    assert len(steps) >= 1
    raw = json.loads((_SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert raw == steps
    for step in steps:
        for call in step.get("tool_calls") or []:
            assert call["name"] in _TOOL_NAMES
