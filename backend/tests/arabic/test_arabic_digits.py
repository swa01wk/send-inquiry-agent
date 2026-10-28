"""Arabic-Indic digits go through every numeric rule (L3 §3.10)."""

import pytest
from app.agent.contact_infer import parse_contact_from_message
from app.agent.guard import _current_turn, message_likely_has_inquiry_data
from app.agent.state import initial_agent_state
from app.domain import validation as v
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey
from langchain_core.messages import HumanMessage


def test_normalise_digits_both_arabic_scripts() -> None:
    assert v.normalise_digits("٠١٢٣٤٥٦٧٨٩") == "0123456789"
    assert v.normalise_digits("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
    assert v.normalise_digits("CR ١٠١٠ abc") == "CR 1010 abc"


@pytest.mark.parametrize("raw", ["١٠١٠١٢٣٤٥٦", "۱۰۱۰۱۲۳۴۵۶", "1010123456"])
def test_cr_number(raw: str) -> None:
    assert v.validate_cr_number(raw) == "1010123456"


def test_cr_rejects_other_unicode_digits() -> None:
    # Devanagari digits are digits to Python's \\d, but not a CR number.
    assert isinstance(v.validate_cr_number("१०१०१२३४५६"), v.ValidationError)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("٠٥٠١٢٣٤٥٦٧", ("mobile", "+966501234567")),
        ("۰۵۰۱۲۳۴۵۶۷", ("mobile", "+966501234567")),
        ("+٩٦٦٥٠١٢٣٤٥٦٧", ("mobile", "+966501234567")),
        ("٠١١٢٣٤٥٦٧٨", ("landline", "+966112345678")),
    ],
)
def test_contact_numbers(raw: str, expected: tuple[str, str]) -> None:
    assert v.classify_contact_number(raw) == expected


def test_vat_national_id_area_rent() -> None:
    assert v.validate_vat_number("٣١٢٣٤٥٦٧٨٩٠١٢٣٣") == "312345678901233"
    assert v.validate_national_id_number("١٠٢٣٤٥٦٧٨٩") == "1023456789"
    assert v.validate_area_min("٣٠") == 30
    assert v.validate_area_max("۱۲۰") == 120
    assert v.validate_rent_min("٥٠٠٠٠") == 50000
    assert v.validate_rent_max("٦٠٠٠٠") == 60000


def test_write_contact_number_in_arabic_digits() -> None:
    draft, written, errors = write_fields(
        new_inquiry_draft(),
        [("contact_number", "٠٥٠١٢٣٤٥٦٧", "user")],  # type: ignore[list-item]
        master=load_master_data(),
    )
    assert not errors
    assert draft.fields[FieldKey.MOBILE].value == "+966501234567"
    assert written == ["mobile"]


def test_contact_line_with_arabic_digits_is_detected() -> None:
    parsed = parse_contact_from_message("سارة علي sara@beanstreet.example ٠٥٠١٢٣٤٥٦٧")
    assert parsed is not None
    first, last, email, phone = parsed
    assert (first, last, email) == ("سارة", "علي", "sara@beanstreet.example")
    assert phone == "0501234567"


def test_capture_heuristic_sees_arabic_digits() -> None:
    assert message_likely_has_inquiry_data("رقم السجل ١٠١٠١٢٣٤٥٦")
    assert message_likely_has_inquiry_data("جوالي ٠٥٠١٢٣٤٥٦٧")


def test_guard_reads_the_turn_with_ascii_digits() -> None:
    state = initial_agent_state(session_id="s", draft=new_inquiry_draft(), phase="gate")
    state["messages"] = [HumanMessage(content="السجل التجاري ١٠١٠١٢٣٤٥٦")]
    text, _ = _current_turn(state)
    assert "1010123456" in text
