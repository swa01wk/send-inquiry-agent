from app.agent.guard import _unknown_mall_note
from app.domain.master import load_master_data
from langchain_core.messages import AIMessage, HumanMessage


def test_unknown_mall_note_when_user_named_red_sea() -> None:
    master = load_master_data()
    user_text = "Bean Street kiosk at Red Sea Mall."
    messages = [
        HumanMessage(content=user_text),
        AIMessage(content="Noted."),
    ]
    note = _unknown_mall_note(user_text, master, messages)
    assert note is not None
    assert "Red Sea Mall" in note
    assert "show_mall_picker" in note


def test_no_note_when_picker_already_shown() -> None:
    master = load_master_data()
    user_text = "Bean Street kiosk at Red Sea Mall."
    messages = [
        HumanMessage(content=user_text),
        AIMessage(
            content="",
            tool_calls=[{"name": "show_mall_picker", "args": {"city": "jeddah"}, "id": "1"}],
        ),
        AIMessage(content="Pick a mall below."),
    ]
    note = _unknown_mall_note(user_text, master, messages)
    assert note is None
