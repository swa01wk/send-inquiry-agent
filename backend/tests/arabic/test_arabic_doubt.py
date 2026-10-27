"""Doubt keeps a derived value unconfirmed, in English and Arabic, for every derived field
(L3 §3.10)."""

import pytest
from app.agent.confirm_policy import expresses_general_doubt, keys_blocked_from_confirmation
from app.agent.guard import _unconfirm_doubted_fields
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, FieldValue, Source
from langchain_core.messages import HumanMessage


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("مو متأكد من الفئة", "sales_category"),
        ("الفئة مو متأكد منها", "sales_category"),
        ("لست متأكدا من التصنيف", "sales_category"),
        ("يمكن غلط نوع الوحدة", "unit_type"),
        ("مش متأكد من الاسم العربي", "brand_name_ar"),
        ("ما أدري عن المساحة", "area_min"),
        ("not sure about the category", "sales_category"),
        ("the category, not sure", "sales_category"),
        ("the unit type might be wrong", "unit_type"),
        ("not sure the Arabic name is right", "brand_name_ar"),
        ("hmm, not sure about the company name", "company_name"),
        ("I don't know about the rent", "rent_min"),
        ("not sure that's the right mall", "malls"),
    ],
)
def test_doubt_blocks_the_named_field(text: str, key: str) -> None:
    assert key in keys_blocked_from_confirmation(text)


@pytest.mark.parametrize(
    "text",
    [
        "Yes, that's all correct",
        "نعم صحيح",
        "تمام، كل شي صحيح",
        "Bean Street kiosk Riyadh Mall A 30 sqm",
        "[ui_event] fields_confirmed sales_category",
    ],
)
def test_acceptance_blocks_nothing(text: str) -> None:
    assert keys_blocked_from_confirmation(text) == frozenset()
    assert not expresses_general_doubt(text)


@pytest.mark.parametrize("text", ["مو متأكد", "hmm, not sure", "ما أدري", "not so sure"])
def test_short_doubt_without_a_field_is_general(text: str) -> None:
    assert keys_blocked_from_confirmation(text) == frozenset()
    assert expresses_general_doubt(text)


def test_long_message_is_not_general_doubt() -> None:
    text = "I'm not sure when we open, but everything on the card looks right to me, thanks"
    assert not expresses_general_doubt(text)


def _state(draft, text: str, **extra):
    state = initial_agent_state(session_id="s", draft=draft, phase="collecting", **extra)
    state["messages"] = [HumanMessage(content=text)]
    return state


def test_guard_unconfirms_doubted_derived_value_in_arabic() -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe", source=Source.DERIVED, confirmed=True
    )
    updated, changed = _unconfirm_doubted_fields(_state(draft, "مو متأكد من الفئة"))
    assert changed == ["sales_category"]
    assert updated.fields[FieldKey.SALES_CATEGORY].confirmed is False


def test_guard_leaves_values_the_user_typed() -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.MALLS] = FieldValue(
        value=["riyadh-mall-a"], source=Source.USER, confirmed=True
    )
    updated, changed = _unconfirm_doubted_fields(_state(draft, "not sure about the mall"))
    assert changed == []
    assert updated.fields[FieldKey.MALLS].confirmed is True
