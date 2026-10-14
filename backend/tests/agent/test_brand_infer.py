from app.agent.brand_infer import (
    extract_arabic_brand_from_message,
    extract_latin_brand_from_message,
    fill_brands_from_user_message,
    fill_missing_brand_name_en,
)
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source


def test_extract_arabic_brand_label() -> None:
    text = "اسم العلامة بين ستريت، كشك قهوة مختصة في Riyadh Mall A"
    assert extract_arabic_brand_from_message(text) == "بين ستريت"


def test_latin_paren_fills_en() -> None:
    assert extract_latin_brand_from_message("Bean Street (بين ستريت) café") == "Bean Street"


def test_fill_brand_en_when_ar_user_and_paren_in_message() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.BRAND_NAME_AR.value, "بين ستريت", Source.USER)],
        master=master,
    )
    user_text = "Bean Street (بين ستريت) specialty café at Riyadh Mall A"
    updated, filled = fill_missing_brand_name_en(draft, user_text)
    assert filled is True
    assert updated.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
    assert updated.fields[FieldKey.BRAND_NAME_EN].source == Source.USER
    assert updated.fields[FieldKey.BRAND_NAME_EN].confirmed is True


def test_fill_both_brands_from_paren_without_prior_draft() -> None:
    draft = new_inquiry_draft()
    user_text = (
        "Acme Trading LLC on King Abdullah Road. Bean Street (بين ستريت) specialty café "
        "at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567."
    )
    updated, changed = fill_brands_from_user_message(draft, user_text)
    assert FieldKey.BRAND_NAME_EN.value in changed
    assert FieldKey.BRAND_NAME_AR.value in changed
    assert updated.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
    assert updated.fields[FieldKey.BRAND_NAME_AR].value == "بين ستريت"
    assert updated.fields[FieldKey.BRAND_NAME_EN].source == Source.USER


def test_paren_en_fills_when_user_stated_it_even_if_ar_derived() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.VERIFIED),
            (FieldKey.BRAND_NAME_AR.value, "بين ستريت", Source.DERIVED),
        ],
        master=master,
    )
    user_text = "Bean Street (بين ستريت) at Riyadh Mall A"
    updated, filled = fill_missing_brand_name_en(draft, user_text)
    assert filled is True
    assert updated.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
    assert updated.fields[FieldKey.BRAND_NAME_EN].source == Source.USER
    assert updated.fields[FieldKey.BRAND_NAME_AR].source == Source.DERIVED
