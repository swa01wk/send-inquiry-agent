"""Agent history trimming at turn boundaries."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.history import trim_messages_for_model


def test_trim_starts_at_user_message_not_mid_tool_pair() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="c1"),
        HumanMessage(content="next"),
        AIMessage(content="reply"),
    ]
    trimmed = trim_messages_for_model(messages, limit=3)
    assert trimmed[0] == messages[2] or isinstance(trimmed[0], HumanMessage)
    assert not any(isinstance(m, ToolMessage) for m in trimmed[:1])


def test_trim_keeps_ui_event_boundary() -> None:
    messages = [
        HumanMessage(content="old"),
        HumanMessage(content="[ui_event] confirm ok"),
        AIMessage(content="thanks"),
    ]
    trimmed = trim_messages_for_model(messages, limit=2)
    assert trimmed[0].content == "[ui_event] confirm ok"
