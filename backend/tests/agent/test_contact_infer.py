import pytest
from app.agent.contact_infer import (
    message_has_contact_line,
    parse_contact_from_message,
)


@pytest.mark.parametrize(
    "user_text",
    [
        "Sara Ali, sara@beanstreet.example, 0501234567",
        "Sara Ali sara@beanstreet.example +966501234567",
        "سارة علي، sara@beanstreet.example، 0501234567",
        "Contact Sara Ali at sara@x.sa / +966501234567",
    ],
)
def test_parse_contact_line(user_text: str) -> None:
    parsed = parse_contact_from_message(user_text)
    assert parsed is not None
    first, last, email, _phone = parsed
    assert first in ("Sara", "سارة")
    assert last in ("Ali", "علي")
    assert email in ("sara@beanstreet.example", "sara@x.sa")


def test_three_part_name() -> None:
    text = "Abdullah Al Harbi, abdullah@beanstreet.example, 0551234567"
    parsed = parse_contact_from_message(text)
    assert parsed is not None
    assert parsed[0] == "Abdullah"
    assert parsed[1] == "Al Harbi"


def test_parse_contact_no_phone_inside_cr() -> None:
    text = "My CR is 1010123456. Sara Ali, sara@x.sa"
    assert parse_contact_from_message(text) is None
    assert not message_has_contact_line(text)


def test_parse_contact_after_bulk_preamble() -> None:
    text = (
        "Acme Trading LLC on King Abdullah Road. Bean Street (بين ستريت) "
        "at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567."
    )
    parsed = parse_contact_from_message(text)
    assert parsed is not None
    assert parsed[0] == "Sara"
    assert parsed[1] == "Ali"


def test_message_has_contact_line() -> None:
    assert message_has_contact_line("Sara Ali, sara@beanstreet.example, 0501234567")
    assert not message_has_contact_line("Just asking about malls")
