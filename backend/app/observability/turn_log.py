"""Structured JSON logs for chat turns (no PII at INFO)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

logger = logging.getLogger(__name__)


def tools_called_from_messages(messages: list[BaseMessage]) -> list[str]:
    names: list[str] = []
    for message in messages:
        if not isinstance(message, AIMessage) or not message.tool_calls:
            continue
        for call in message.tool_calls:
            if isinstance(call, dict):
                name = call.get("name")
            else:
                name = getattr(call, "name", None)
            if isinstance(name, str) and name:
                names.append(name)
    return names


def assistant_text_chars(messages: list[BaseMessage]) -> int:
    total = 0
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        content = message.content
        if isinstance(content, str):
            total += len(content)
    return total


def log_chat_turn(
    *,
    session_id: str,
    phase: str,
    messages: list[BaseMessage],
    latency_ms: float,
    streamed_token_chars: int,
    outcome: str,
    retractions: int = 0,
) -> None:
    payload: dict[str, Any] = {
        "event": "chat_turn",
        "session_id": session_id,
        "phase": phase,
        "tools_called": tools_called_from_messages(messages),
        "latency_ms": round(latency_ms, 1),
        "streamed_token_chars": streamed_token_chars,
        "assistant_text_chars": assistant_text_chars(messages),
        "retractions": retractions,
        "outcome": outcome,
    }
    logger.info(json.dumps(payload, separators=(",", ":")))


class TurnTimer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
