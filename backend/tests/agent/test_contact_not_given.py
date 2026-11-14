"""update_draft refuses contact details the user never typed (F5 evals, S16: on "how long
does the review take?" the model saved an invented contact)."""

from __future__ import annotations

import pytest
from app.agent.tools import DraftFieldUpdate, _contact_not_given, _normalise_quote


def _said(*messages: str) -> str:
    return _normalise_quote(" \n ".join(messages))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("first_name", "Sara"),
        ("last_name", "Ali"),
        ("email", "sara@beanstreet.example"),
        ("contact_number", "0501234567"),
    ],
)
def test_invented_contact_is_refused(key: str, value: str) -> None:
    said = _said("we sell specialty coffee", "how long does the review take?")
    assert _contact_not_given(DraftFieldUpdate(key=key, value=value, source="user"), said)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("first_name", "Sara"),
        ("last_name", "Al-Ali"),
        ("email", "Sara@BeanStreet.example"),
        ("contact_number", "+966501234567"),
        ("mobile", "0501234567"),
    ],
)
def test_typed_contact_is_kept(key: str, value: str) -> None:
    said = _said("Sara Al-Ali, sara@beanstreet.example, ٠٥٠١٢٣٤٥٦٧")
    assert not _contact_not_given(DraftFieldUpdate(key=key, value=value, source="user"), said)


def test_arabic_writer_keeps_a_transliterated_name_and_derived_values_pass() -> None:
    said = _said("اسمي سارة علي")
    assert not _contact_not_given(
        DraftFieldUpdate(key="first_name", value="Sara", source="user"), said
    )
    assert not _contact_not_given(
        DraftFieldUpdate(key="email", value="x@y.example", source="derived"), _said("hi")
    )
