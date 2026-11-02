"""Bounded model history (M0 §5.5)."""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage


def _is_user_turn_start(message: BaseMessage) -> bool:
    if not isinstance(message, HumanMessage):
        return False
    text = str(message.content).strip()
    if not text:
        return False
    if text.startswith("[guard]"):
        return False
    return True


def trim_messages_for_model(messages: list[BaseMessage], limit: int) -> list[BaseMessage]:
    """Keep the last ``limit`` messages, cutting only before a user or [ui_event] turn."""
    if limit <= 0 or len(messages) <= limit:
        return messages
    start = len(messages) - limit
    while start > 0 and not _is_user_turn_start(messages[start]):
        start += 1
    if start >= len(messages):
        return messages[-limit:]
    return messages[start:]
