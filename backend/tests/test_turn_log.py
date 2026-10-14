from app.observability.turn_log import tools_called_from_messages
from langchain_core.messages import AIMessage, HumanMessage


def test_tools_called_from_messages() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(
            content="",
            tool_calls=[{"name": "verify_cr", "args": {}, "id": "1", "type": "tool_call"}],
        ),
        AIMessage(content="Thanks"),
    ]
    assert tools_called_from_messages(messages) == ["verify_cr"]
