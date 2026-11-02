"""Compare replayed parity streams to golden transcripts."""

from __future__ import annotations

import json
from typing import Any


def _event_types(events: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("event")) for item in events]


def _ui_cards(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item["data"] for item in events if item.get("event") == "ui_card"]


def _draft_changed_keys(events: list[dict[str, Any]]) -> list[list[str]]:
    out: list[list[str]] = []
    for item in events:
        if item.get("event") != "draft":
            continue
        data = item.get("data") or {}
        keys = data.get("changed_keys")
        out.append(list(keys) if isinstance(keys, list) else [])
    return out


def _final_phase(events: list[dict[str, Any]]) -> str | None:
    for item in reversed(events):
        if item.get("event") == "done":
            data = item.get("data") or {}
            phase = data.get("phase")
            return str(phase) if phase is not None else None
    return None


def _final_draft(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(events):
        if item.get("event") == "draft":
            data = item.get("data")
            return data if isinstance(data, dict) else None
    return None


def _reply_text_by_message_id(events: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Concatenate token text per message_id, ignoring removed messages."""
    removed: set[str] = set()
    parts: dict[str, str] = {}
    order: list[str] = []
    for item in events:
        event_type = item.get("event")
        data = item.get("data") or {}
        if event_type == "message_remove":
            removed.add(str(data.get("message_id", "")))
            continue
        if event_type != "token":
            continue
        message_id = str(data.get("message_id", ""))
        if message_id in removed:
            continue
        if message_id not in parts:
            order.append(message_id)
        parts[message_id] = parts.get(message_id, "") + str(data.get("text", ""))
    return [(mid, parts[mid]) for mid in order]


def _payload_diff_paths(expected: Any, actual: Any, *, prefix: str = "") -> list[str]:
    if expected == actual:
        return []
    if isinstance(expected, dict) and isinstance(actual, dict):
        paths: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in expected:
                paths.append(f"{path} (missing in expected)")
            elif key not in actual:
                paths.append(f"{path} (missing in actual)")
            else:
                paths.extend(_payload_diff_paths(expected[key], actual[key], prefix=path))
        return paths
    if isinstance(expected, list) and isinstance(actual, list):
        paths = []
        max_len = max(len(expected), len(actual))
        for index in range(max_len):
            path = f"{prefix}[{index}]"
            if index >= len(expected):
                paths.append(f"{path} (missing in expected)")
            elif index >= len(actual):
                paths.append(f"{path} (missing in actual)")
            else:
                paths.extend(_payload_diff_paths(expected[index], actual[index], prefix=path))
        return paths
    return [prefix or "(root)"]


def compare_streams(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
) -> list[str]:
    """Return human-readable diff lines; empty when equal."""
    diffs: list[str] = []
    if _event_types(expected) != _event_types(actual):
        diffs.append("event order:")
        diffs.append(f"  expected: {_event_types(expected)}")
        diffs.append(f"  actual:   {_event_types(actual)}")
    exp_cards = _ui_cards(expected)
    act_cards = _ui_cards(actual)
    if len(exp_cards) != len(act_cards):
        diffs.append(f"ui_card count: expected {len(exp_cards)}, got {len(act_cards)}")
    for index, (exp, act) in enumerate(zip(exp_cards, act_cards, strict=False)):
        if exp.get("card_type") != act.get("card_type"):
            diffs.append(
                f"ui_card[{index}] type: expected {exp.get('card_type')!r}, "
                f"got {act.get('card_type')!r}"
            )
        if exp.get("payload") != act.get("payload"):
            diffs.append(f"ui_card[{index}] payload mismatch ({exp.get('card_type')}):")
            for path in _payload_diff_paths(exp.get("payload"), act.get("payload")):
                diffs.append(f"  differs: {path}")
            diffs.append(
                "  expected: " + json.dumps(exp.get("payload"), ensure_ascii=False, sort_keys=True)
            )
            diffs.append(
                "  actual:   " + json.dumps(act.get("payload"), ensure_ascii=False, sort_keys=True)
            )
    exp_replies = _reply_text_by_message_id(expected)
    act_replies = _reply_text_by_message_id(actual)
    if exp_replies != act_replies:
        diffs.append("reply text by message_id:")
        diffs.append(f"  expected: {exp_replies}")
        diffs.append(f"  actual:   {act_replies}")
    if _draft_changed_keys(expected) != _draft_changed_keys(actual):
        diffs.append("draft changed_keys sequence:")
        diffs.append(f"  expected: {_draft_changed_keys(expected)}")
        diffs.append(f"  actual:   {_draft_changed_keys(actual)}")
    if _final_phase(expected) != _final_phase(actual):
        diffs.append(
            f"final phase: expected {_final_phase(expected)!r}, got {_final_phase(actual)!r}"
        )
    if _final_draft(expected) != _final_draft(actual):
        diffs.append("final draft mismatch:")
        diffs.append(
            "  expected: "
            + json.dumps(_final_draft(expected), ensure_ascii=False, sort_keys=True)[:2000]
        )
        diffs.append(
            "  actual:   "
            + json.dumps(_final_draft(actual), ensure_ascii=False, sort_keys=True)[:2000]
        )
    return diffs
