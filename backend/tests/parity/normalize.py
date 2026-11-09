"""Normalise volatile fields in recorded SSE payloads for golden comparison."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(r"^GEO-(STR|MED|SPC)-(\d{6})$")
_ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
_FILE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
# Document evidence (domain/document_fill.document_evidence): "<label>: <file>, uploaded <time>".
_UPLOADED_AT_RE = re.compile(r"uploaded \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}")


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _normalise_string(value: str, *, message_ids: dict[str, str]) -> str:
    if value in message_ids:
        return message_ids[value]
    if _is_uuid(value):
        return "SESSION_ID"
    ref = _REFERENCE_RE.match(value)
    if ref:
        return f"GEO-{ref.group(1)}-<ref>"
    if _ISO_TS_RE.match(value):
        return "TIMESTAMP"
    if _FILE_ID_RE.match(value):
        return "FILE_ID"
    return _UPLOADED_AT_RE.sub("uploaded UPLOAD_TIME", value)


def _walk(node: Any, message_ids: dict[str, str]) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "message_id" and isinstance(value, str):
                if value not in message_ids:
                    message_ids[value] = f"m{len(message_ids) + 1}"
                out[key] = message_ids[value]
                continue
            if key == "demo_token" and isinstance(value, str):
                out[key] = "EMAIL_TOKEN"
                continue
            if key == "session_id" and isinstance(value, str) and _is_uuid(value):
                out[key] = "SESSION_ID"
                continue
            if key == "uploaded_at" and isinstance(value, str):
                out[key] = "TIMESTAMP"
                continue
            if key == "file_id" and isinstance(value, str):
                out[key] = "FILE_ID"
                continue
            if key == "reference" and isinstance(value, str):
                ref = _REFERENCE_RE.match(value)
                out[key] = f"GEO-{ref.group(1)}-<ref>" if ref else value
                continue
            if key == "resend_available_at" and value is not None:
                out[key] = "TIMESTAMP" if isinstance(value, str) else value
                continue
            out[key] = _walk(value, message_ids)
        return out
    if isinstance(node, list):
        return [_walk(item, message_ids) for item in node]
    if isinstance(node, str):
        return _normalise_string(node, message_ids=message_ids)
    return node


def normalize_events(events: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Return JSON-serialisable records with stable ids and timestamps."""
    message_ids: dict[str, str] = {}
    normalised: list[dict[str, Any]] = []
    for event_type, data in events:
        payload = _walk(copy.deepcopy(data), message_ids)
        normalised.append({"event": event_type, "data": payload})
    return normalised


def events_from_jsonl(text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def chat_turns_for_script(
    script: list[Any],
    events: list[dict[str, Any]],
) -> list[tuple[Any, list[dict[str, Any]]]]:
    """Pair each non-upload script step with its SSE turn (split on ``done``)."""
    turns = split_turns(events)
    paired: list[tuple[Any, list[dict[str, Any]]]] = []
    turn_index = 0
    for step in script:
        if getattr(step, "kind", None) == "upload":
            continue
        assert turn_index < len(turns), "fewer chat turns than script steps"
        paired.append((step, turns[turn_index]))
        turn_index += 1
    assert turn_index == len(turns), "more chat turns than script steps"
    return paired


def split_turns(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    turns: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for item in events:
        current.append(item)
        if item.get("event") == "done":
            turns.append(current)
            current = []
    if current:
        turns.append(current)
    return turns
