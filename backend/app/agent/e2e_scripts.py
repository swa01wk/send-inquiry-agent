"""Load Playwright e2e scripted agent steps from JSON."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agent.model import ScriptedChatModel

_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "tests" / "e2e_scripts"


@lru_cache
def list_e2e_script_names() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in _SCRIPTS_DIR.glob("*.json")))


def load_e2e_script_steps(name: str) -> list[dict[str, Any]]:
    path = _SCRIPTS_DIR / f"{name}.json"
    if not path.is_file():
        msg = f"Unknown e2e script: {name}"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        msg = f"E2e script must be a JSON array: {name}"
        raise ValueError(msg)
    return data


def scripted_model_for_session(*, scenario: str, step_index: int) -> ScriptedChatModel:
    steps = load_e2e_script_steps(scenario)
    model = ScriptedChatModel(steps=steps)
    model._step_index = step_index
    return model
