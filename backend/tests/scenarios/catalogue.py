"""Load scenario definitions from tests/scenarios/catalogue/*.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

Layer = Literal["e2e_script", "agent_det"]

_CATALOGUE_DIR = Path(__file__).resolve().parent / "catalogue"
_SHARED_PATH = _CATALOGUE_DIR / "_shared.yaml"

HAND_WRITTEN_E2E_SCRIPTS = frozenset(
    {
        "a1-existing-tenant",
        "a2-applicant",
        "a2-call-centre",
        "c1-existing-cr",
        "c1-existing-cr-sign-in",
        "r1-yardi-suggest",
        "r2-tenant-reminder",
        "s1-happy-path",
        "s13-form-mode",
        "s3-submit-timeout",
        "t1-contacts",
        "t2-reupload",
    }
)


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache
def _shared_fragments() -> dict[str, Any]:
    if not _SHARED_PATH.is_file():
        return {}
    data = _load_yaml(_SHARED_PATH)
    return data if isinstance(data, dict) else {}


def _resolve_aliases(node: Any, shared: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if len(node) == 1 and "ref" in node and isinstance(node["ref"], str):
            key = node["ref"]
            if key not in shared:
                msg = f"unknown catalogue ref: {key}"
                raise KeyError(msg)
            return _resolve_aliases(shared[key], shared)
        return {k: _resolve_aliases(v, shared) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_aliases(item, shared) for item in node]
    return node


@lru_cache
def _all_entries() -> dict[str, dict[str, Any]]:
    shared = _shared_fragments()
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(_CATALOGUE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = _load_yaml(path)
        if not isinstance(raw, dict):
            continue
        entry_id = str(raw.get("id") or path.stem)
        raw["id"] = entry_id
        entries[entry_id] = _resolve_aliases(raw, shared)
    return entries


def load_catalogue_entry(entry_id: str) -> dict[str, Any]:
    entries = _all_entries()
    if entry_id not in entries:
        msg = f"unknown catalogue entry: {entry_id}"
        raise KeyError(msg)
    return entries[entry_id]


def list_by_layer(layer: Layer) -> list[str]:
    out: list[str] = []
    for entry_id, entry in _all_entries().items():
        layers = entry.get("layers") or []
        if layer in layers:
            out.append(entry_id)
    return sorted(out)


def model_steps_for(entry_id: str) -> list[dict[str, Any]]:
    entry = load_catalogue_entry(entry_id)
    steps = entry.get("model_steps")
    if not isinstance(steps, list):
        msg = f"catalogue entry {entry_id} has no model_steps"
        raise ValueError(msg)
    return steps


def user_turns_for(entry_id: str) -> list[dict[str, Any]]:
    entry = load_catalogue_entry(entry_id)
    turns = entry.get("user_turns") or []
    if not isinstance(turns, list):
        msg = f"catalogue entry {entry_id} user_turns must be a list"
        raise ValueError(msg)
    return turns


def e2e_script_json_text(entry_id: str) -> str:
    """Same serialization as generate_e2e_scripts.py."""
    import json

    steps = model_steps_for(entry_id)
    return json.dumps(steps, indent=2, ensure_ascii=False) + "\n"


def clear_catalogue_cache() -> None:
    _shared_fragments.cache_clear()
    _all_entries.cache_clear()
