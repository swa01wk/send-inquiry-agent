from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agent.case_tools import CASE_TOOLS
from app.agent.e2e_scripts import list_e2e_script_names, load_e2e_script_steps
from app.agent.reviewer_tools import REVIEWER_TOOLS
from app.agent.tools import ASSISTED_TOOLS, TOOLS

pytestmark = pytest.mark.agent

_TOOL_NAMES = (
    {t.name for t in TOOLS}
    | {t.name for t in CASE_TOOLS}
    | {t.name for t in ASSISTED_TOOLS}
    | {t.name for t in REVIEWER_TOOLS}
)
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


_TOOLS_BY_NAME = {t.name: t for t in (*TOOLS, *CASE_TOOLS, *ASSISTED_TOOLS, *REVIEWER_TOOLS)}


@pytest.mark.parametrize("name", list_e2e_script_names())
def test_e2e_script_tool_args_match_the_tool(name: str) -> None:
    """A wrong argument name makes the scripted tool call fail, and the model is called again:
    every later turn then plays the wrong step (rd-type-or-upload used `suggestions` for
    suggest_replies' `options`)."""
    for index, step in enumerate(load_e2e_script_steps(name)):
        for call in step.get("tool_calls") or []:
            schema = _TOOLS_BY_NAME[call["name"]].tool_call_schema
            assert isinstance(schema, type), call["name"]
            try:
                schema.model_validate(call.get("args") or {})  # type: ignore[attr-defined]
            except Exception as err:  # pydantic.ValidationError
                pytest.fail(f"{name} step {index}: {call['name']} args: {err}")
