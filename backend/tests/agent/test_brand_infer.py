from app.agent.brand_infer import (
    brand_en_from_company_name,
    extract_arabic_brand_from_message,
    fill_missing_brand_name_en,
)
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source


def test_brand_en_from_bean_street_trading_co() -> None:
    assert brand_en_from_company_name("Bean Street Trading Co.") == "Bean Street"


def test_extract_arabic_brand_label() -> None:
    text = "اسم العلامة بين ستريت، كشك قهوة مختصة في Riyadh Mall A"
    assert extract_arabic_brand_from_message(text) == "بين ستريت"


def test_fill_brand_en_when_ar_set_and_company_on_cr() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.VERIFIED),
            (FieldKey.BRAND_NAME_AR.value, "بين ستريت", Source.USER),
        ],
        master=master,
    )
    user_text = "اسم العلامة بين ستريت، كشك قهوة مختصة في Riyadh Mall A"
    updated, filled = fill_missing_brand_name_en(draft, user_text)
    assert filled is True
    assert updated.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
    assert updated.fields[FieldKey.BRAND_NAME_EN].source == Source.DERIVED


def test_fill_brand_ar_and_en_from_arabic_only_turn() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.VERIFIED)],
        master=master,
    )
    user_text = "اسم العلامة بين ستريت، كشك قهوة مختصة في Riyadh Mall A"
    updated, filled = fill_missing_brand_name_en(draft, user_text)
    assert filled is True
    assert updated.fields[FieldKey.BRAND_NAME_AR].value == "بين ستريت"
    assert updated.fields[FieldKey.BRAND_NAME_EN].value == "Bean Street"
