import pytest
from app.agent.contact_infer import (
    fill_contact_from_user_message,
    message_has_contact_line,
    parse_contact_from_message,
)
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source


@pytest.mark.parametrize(
    "user_text",
    [
        "Sara Ali, sara@beanstreet.example, 0501234567",
        "Sara Ali sara@beanstreet.example +966501234567",
        "سارة علي، sara@beanstreet.example، 0501234567",
    ],
)
def test_parse_contact_line(user_text: str) -> None:
    parsed = parse_contact_from_message(user_text)
    assert parsed is not None
    first, last, email, _phone = parsed
    assert first in ("Sara", "سارة")
    assert last in ("Ali", "علي")
    assert email == "sara@beanstreet.example"


def test_fill_contact_on_empty_draft() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    text = "Sara Ali, sara@beanstreet.example, 0501234567"
    updated, changed = fill_contact_from_user_message(draft, text, master=master)
    assert FieldKey.FIRST_NAME.value in changed
    assert FieldKey.LAST_NAME.value in changed
    assert FieldKey.EMAIL.value in changed
    assert FieldKey.MOBILE.value in changed
    assert updated.fields[FieldKey.FIRST_NAME].value == "Sara"
    assert updated.fields[FieldKey.LAST_NAME].value == "Ali"
    assert updated.fields[FieldKey.EMAIL].value == "sara@beanstreet.example"
    assert updated.fields[FieldKey.MOBILE].value == "+966501234567"
    assert updated.fields[FieldKey.FIRST_NAME].source == Source.USER
    assert updated.fields[FieldKey.FIRST_NAME].confirmed is True


def test_fill_contact_does_not_overwrite_existing() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.EMAIL.value, "other@example.com", Source.USER)],
        master=master,
    )
    text = "Sara Ali, sara@beanstreet.example, 0501234567"
    updated, changed = fill_contact_from_user_message(draft, text, master=master)
    assert FieldKey.EMAIL.value not in changed
    assert updated.fields[FieldKey.EMAIL].value == "other@example.com"


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
