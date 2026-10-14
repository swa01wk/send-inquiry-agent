from app.agent.bundles import next_bundle_hint
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, FieldValue, Source


def _set(draft, key: FieldKey, value, source=Source.USER, confirmed=True) -> None:
    draft.fields[key] = FieldValue(value=value, source=source, confirmed=confirmed)


def test_gate_asks_for_cr() -> None:
    hint = next_bundle_hint(new_inquiry_draft())
    assert "CR number" in hint


def test_skipped_cr_asks_company_name_and_address_together() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    hint = next_bundle_hint(draft)
    assert "Company name" in hint and "Company address" in hint
    assert "together" in hint


def test_brand_bundle_asks_once_and_skips_inferable_fields() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "new"
    _set(draft, FieldKey.COMPANY_NAME, "Bean Street Trading Co.")
    _set(draft, FieldKey.COMPANY_ADDRESS, "King Fahd Road, Riyadh")
    hint = next_bundle_hint(draft)
    assert "brand and space" in hint
    assert "Brand name (AR)" not in hint.split("Next question")[1].split("\n")[0]
    assert "optional" in hint


def test_otp_already_sent_hint() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "new"
    _set(draft, FieldKey.COMPANY_NAME, "Bean Street Trading Co.")
    _set(draft, FieldKey.COMPANY_ADDRESS, "King Fahd Road, Riyadh")
    _set(draft, FieldKey.BRAND_NAME_EN, "Bean Street")
    _set(draft, FieldKey.BRAND_NAME_AR, "بين ستريت", Source.DERIVED, confirmed=True)
    _set(draft, FieldKey.UNIT_TYPE, "specialty", Source.DERIVED, confirmed=True)
    _set(draft, FieldKey.SALES_CATEGORY, "fnb_cafe", Source.DERIVED, confirmed=True)
    _set(draft, FieldKey.MALLS, ["riyadh-mall-a"])
    _set(draft, FieldKey.FIRST_NAME, "Sara")
    _set(draft, FieldKey.LAST_NAME, "Ali")
    _set(draft, FieldKey.EMAIL, "sara@example.com")
    _set(draft, FieldKey.MOBILE, "0501234567")
    draft.otp_verified = False
    hint = next_bundle_hint(draft, cards_shown=["otp"])
    assert "Verification code already sent" in hint
    assert "send_otp" not in hint


def test_contact_bundle_after_brand() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "new"
    _set(draft, FieldKey.COMPANY_NAME, "Bean Street Trading Co.")
    _set(draft, FieldKey.COMPANY_ADDRESS, "King Fahd Road, Riyadh")
    _set(draft, FieldKey.BRAND_NAME_EN, "Bean Street")
    _set(draft, FieldKey.BRAND_NAME_AR, "بين ستريت", Source.DERIVED, confirmed=False)
    _set(draft, FieldKey.UNIT_TYPE, "specialty", Source.DERIVED, confirmed=False)
    _set(draft, FieldKey.SALES_CATEGORY, "fnb_cafe", Source.DERIVED, confirmed=False)
    _set(draft, FieldKey.MALLS, ["riyadh-mall-a"])
    hint = next_bundle_hint(draft)
    assert "contact" in hint
    assert "Phone number" in hint
    assert "not yet accepted" in hint
