import pytest
from app.domain import validation as v
from app.domain.master import load_master_data


@pytest.fixture
def master():
    return load_master_data()


def test_cr_number_valid_and_invalid():
    assert v.validate_cr_number("1010123456") == "1010123456"
    err = v.validate_cr_number("123")
    assert err.code == "invalid_cr_number"


def test_email_valid_and_invalid():
    assert v.validate_email("sara@example.com") == "sara@example.com"
    assert v.validate_email("bad").code == "invalid_email"


def test_brand_scripts():
    assert v.validate_brand_name_en("Bean Street") == "Bean Street"
    assert v.validate_brand_name_en("كافيه").code == "invalid_brand_name_en"
    assert v.validate_brand_name_ar("بين ستريت").startswith("بين")
    assert v.validate_brand_name_ar("Bean").code == "invalid_brand_name_ar"


def test_classify_contact_number():
    mobile = v.classify_contact_number("0501234567")
    assert mobile == ("mobile", "+966501234567")
    landline = v.classify_contact_number("11234567")
    assert landline == ("landline", "+96611234567")
    assert v.classify_contact_number("invalid").code in {
        "invalid_mobile",
        "invalid_landline",
    }


def test_vat_and_national_id():
    assert v.validate_vat_number("300000000000003") == "300000000000003"
    assert v.validate_vat_number("100000000000001").code == "invalid_vat_number"
    assert v.validate_national_id_number("1012345678") == "1012345678"
    assert v.validate_national_id_number("3012345678").code == "invalid_national_id"


def test_area_and_rent_rules():
    assert v.validate_area_min(25) == 25
    assert v.validate_area_min(5).code == "invalid_area_min"
    assert v.validate_area_range(30, 20).code == "invalid_area_range"
    assert v.validate_rent_range(100, 50).code == "invalid_rent_range"
    assert v.validate_rent_period_required(None, 100, None).code == "missing_rent_period"


def test_malls_and_documents(master):
    assert v.validate_malls(["riyadh-mall-a"], master) == ["riyadh-mall-a"]
    assert v.validate_malls([], master).code == "invalid_malls"
    two = v.validate_malls(["riyadh-mall-a", "riyadh-mall-b"], master)
    assert two.code == "one_mall_per_inquiry"
    assert v.validate_malls(["riyadh-mall-a", "riyadh-mall-a"], master) == ["riyadh-mall-a"]
    assert v.validate_document_extension("file.pdf") is None
    assert v.validate_document_extension("file.exe").code == "invalid_extension"
    assert v.validate_document_size(6 * 1024 * 1024, 5 * 1024 * 1024).code == "too_large"


def test_international_numbers():
    # Non-Saudi numbers need a country code and default to mobile.
    assert v.classify_contact_number("+971 50 123 4567") == ("mobile", "+971501234567")
    assert v.classify_contact_number("0044 20 7946 0958") == ("mobile", "+442079460958")
    assert v.normalise_landline("+44 20 7946 0958") == "+442079460958"
    assert v.normalise_mobile("+971501234567") == "+971501234567"
    # +966 keeps the Saudi rules.
    assert v.classify_contact_number("+966 50 123 4567") == ("mobile", "+966501234567")
    assert v.normalise_mobile("+966112345678").code == "invalid_mobile"
    # Too short or too long for E.164.
    assert v.classify_contact_number("+971 123").code == "invalid_phone"
    assert v.classify_contact_number("+1234567890123456").code == "invalid_phone"
