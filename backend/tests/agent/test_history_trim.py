"""Agent history trimming at turn boundaries."""

from app.agent.history import trim_messages_for_model
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_trim_starts_at_user_message_not_mid_tool_pair() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="c1"),
        HumanMessage(content="next"),
        AIMessage(content="reply"),
    ]
    trimmed = trim_messages_for_model(messages, limit=3)
    assert isinstance(trimmed[0], HumanMessage)
    assert not isinstance(trimmed[0], ToolMessage)


def test_trim_never_starts_with_tool_message() -> None:
    messages = [
        HumanMessage(content="a"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="c1"),
        AIMessage(content="done"),
    ]
    trimmed = trim_messages_for_model(messages, limit=2)
    assert trimmed
    assert not isinstance(trimmed[0], ToolMessage)


def test_trim_treats_ui_event_as_turn_start() -> None:
    messages = [
        HumanMessage(content="[ui_event] confirm ok"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="c1"),
        AIMessage(content="end"),
    ]
    trimmed = trim_messages_for_model(messages, limit=3)
    assert trimmed[0].content == "[ui_event] confirm ok"


def test_trim_ui_event_guard_is_not_turn_start() -> None:
    messages = [
        HumanMessage(content="real question"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="c1"),
        HumanMessage(
            content=(
                "[ui_event] guard: The user's last message looks like it contains "
                "inquiry details you did not save."
            )
        ),
        AIMessage(content="retry"),
    ]
    trimmed = trim_messages_for_model(messages, limit=3)
    assert isinstance(trimmed[0], HumanMessage)
    assert trimmed[0].content == "real question"


def test_trim_long_history_ending_in_ui_event_keeps_last_real_user() -> None:
    messages: list = []
    for index in range(20):
        messages.append(HumanMessage(content=f"user-{index}"))
        messages.append(AIMessage(content=f"reply-{index}"))
    messages.append(HumanMessage(content="[ui_event] confirm ok"))
    messages.append(AIMessage(content="thanks"))

    trimmed = trim_messages_for_model(messages, limit=4)
    contents = [str(m.content) for m in trimmed if isinstance(m, HumanMessage)]
    assert "user-19" in contents
