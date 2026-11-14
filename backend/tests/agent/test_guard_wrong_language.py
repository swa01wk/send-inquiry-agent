"""An Arabic-writing user gets Arabic replies (F5 evals, "Arabic user": after a contact
message with a Latin email the agent switched to English)."""

from __future__ import annotations

from typing import Any

from app.agent.guard import _wrong_language_note
from langchain_core.messages import AIMessage, HumanMessage


def _state(*typed: str) -> Any:
    return {"messages": [HumanMessage(content=text) for text in typed]}


def test_english_reply_to_arabic_contact_message_is_flagged() -> None:
    state = _state("سارة علي، sara@beanstreet.example، 0501234567")
    note = _wrong_language_note(state, "Thanks, Sara. I've sent the email link.")
    assert note is not None and "Arabic" in note


def test_arabic_reply_passes() -> None:
    state = _state("سارة علي، sara@beanstreet.example، 0501234567")
    assert _wrong_language_note(state, "شكرًا سارة، أرسلنا رابط التحقق.") is None


def test_card_notes_are_skipped_and_english_users_pass() -> None:
    state = {
        "messages": [
            HumanMessage(content="السلام عليكم، نريد افتتاح كشك قهوة"),
            AIMessage(content="وعليكم السلام"),
            HumanMessage(content="[ui_event] fields_confirmed unit_type"),
        ]
    }
    assert _wrong_language_note(state, "Which mall?") is not None
    assert _wrong_language_note(_state("Bean Street, Riyadh Mall A"), "Thanks!") is None
    # A Latin brand with one Arabic word is still an English message.
    assert _wrong_language_note(_state("Bean Street «بين» at Riyadh Mall A"), "Thanks!") is None


def test_arabic_brand_name_in_an_english_chat_passes() -> None:
    state = _state("I'll upload the Brand Profile", "مخبز الواحة")
    assert _wrong_language_note(state, "Saved. Now upload the Company Profile.") is None
