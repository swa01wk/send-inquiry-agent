"""A bare Store / Office answer is saved by code, and never taken back as "unsaved".

Live eval 16 Nov (Arabic user, 1/3): "متجر" was answered but not saved, or was already
saved, and the missed-capture rule took the reply back.
"""

from __future__ import annotations

import pytest
from app.agent.guard import _missed_capture_note, bare_unit_choice, fill_unit_choice
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("Store", "store"),
        ("a store", "store"),
        ("an office.", "office"),
        ("متجر", "store"),
        ("المتجر", "store"),
        ("مكتب", "office"),
        ("a store in Riyadh Mall A", None),
        ("what's the difference between a store and an office?", None),
        ("", None),
    ],
)
def test_bare_unit_choice(text: str, want: str | None) -> None:
    assert bare_unit_choice(text) == want


def test_fill_writes_the_choice_once() -> None:
    master = load_master_data()
    draft, filled = fill_unit_choice(new_inquiry_draft(), "متجر", master)
    assert filled
    assert draft.fields[FieldKey.UNIT_TYPE].value == "store"
    assert draft.fields[FieldKey.UNIT_TYPE].source == Source.USER
    _same, again = fill_unit_choice(draft, "Store", master)
    assert not again


def _state(text: str, unit: str | None) -> dict:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    draft.fields[FieldKey.UNIT_TYPE].value = unit
    return {
        "messages": [HumanMessage(content=text), AIMessage(content="تم، متجر محفوظ.")],
        "draft": draft,
    }


def test_a_saved_choice_is_not_unsaved_data() -> None:
    assert _missed_capture_note(_state("متجر", "store"), "collecting") is None


def test_unsaved_details_still_get_the_note() -> None:
    note = _missed_capture_note(_state("Sara Ali, sara@beanstreet.example", "store"), "collecting")
    assert note is not None and "did not save" in note
