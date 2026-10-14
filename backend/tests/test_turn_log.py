import json
import logging

from app.observability.turn_log import log_chat_turn, tools_called_from_messages
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


def test_log_chat_turn_includes_retractions(caplog) -> None:
    caplog.set_level(logging.INFO)
    log_chat_turn(
        session_id="s1",
        phase="collecting",
        messages=[],
        latency_ms=12.3,
        streamed_token_chars=0,
        retractions=2,
        outcome="done",
    )
    payload = json.loads(caplog.records[-1].message)
    assert payload["retractions"] == 2
