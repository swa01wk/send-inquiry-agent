"""Bounded model history (M0 §5.5)."""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

GUARD_UI_PREFIX = "[ui_event] guard:"


def _human_text(message: BaseMessage) -> str:
    if not isinstance(message, HumanMessage):
        return ""
    return str(message.content).strip()


def _is_real_user_message(message: BaseMessage) -> bool:
    text = _human_text(message)
    if not text:
        return False
    if text.startswith("[ui_event]"):
        return False
    if text.startswith("[guard]"):
        return False
    return True


def _is_user_turn_start(message: BaseMessage) -> bool:
    text = _human_text(message)
    if not text:
        return False
    if text.startswith("[guard]"):
        return False
    if text.startswith(GUARD_UI_PREFIX):
        return False
    return isinstance(message, HumanMessage)


def _last_real_user_index(messages: list[BaseMessage]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        if _is_real_user_message(messages[index]):
            return index
    return None


def _turn_start_at_or_before(messages: list[BaseMessage], index: int) -> int:
    start = index
    while start > 0 and not _is_user_turn_start(messages[start]):
        start -= 1
    while start < len(messages) and isinstance(messages[start], ToolMessage):
        if start == 0:
            break
        start -= 1
        while start > 0 and not _is_user_turn_start(messages[start]):
            start -= 1
    return start


def trim_messages_for_model(messages: list[BaseMessage], limit: int) -> list[BaseMessage]:
    """Keep roughly the last ``limit`` messages, cut only at a user turn boundary."""
    if limit <= 0 or len(messages) <= limit:
        return messages

    min_start = len(messages) - limit
    start = _turn_start_at_or_before(messages, min_start)

    last_real = _last_real_user_index(messages)
    if last_real is not None and start > last_real:
        start = _turn_start_at_or_before(messages, last_real)

    if len(messages) - start < limit:
        start = _turn_start_at_or_before(messages, min_start)

    return messages[start:]
