from app.agent.bundles import next_bundle_hint
from app.api.channel_cards import basic_info_missing
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


def _ready_for_verification():
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
    _set(draft, FieldKey.MOBILE, "+966501234567")
    return draft


def test_verification_not_sent_hint() -> None:
    hint = next_bundle_hint(_ready_for_verification())
    assert "send_verification" in hint


def test_verification_already_sent_hint() -> None:
    draft = _ready_for_verification()
    draft.email_link_sent_to = "sara@example.com"
    draft.otp_sent_to = "+966501234567"
    hint = next_bundle_hint(draft)
    assert "Verification already sent" in hint
    assert "send_verification" not in hint


def test_verification_resend_hint_after_email_change() -> None:
    draft = _ready_for_verification()
    draft.email_link_sent_to = "old@example.com"
    draft.otp_sent_to = "+966501234567"
    hint = next_bundle_hint(draft)
    assert "send_verification" in hint


def test_landline_only_needs_only_the_email_link() -> None:
    draft = _ready_for_verification()
    _set(draft, FieldKey.MOBILE, None, source=None, confirmed=False)
    _set(draft, FieldKey.LANDLINE, "+96611234567")
    draft.email_link_sent_to = "sara@example.com"
    hint = next_bundle_hint(draft)
    assert "Verification already sent" in hint


def test_assisted_complete_basic_info_hints_show_application_link() -> None:
    draft = _ready_for_verification()
    assert not basic_info_missing(draft)
    hint = next_bundle_hint(draft, assisted=True)
    assert "show_application_link" in hint
    assert "send_verification" not in hint


def test_assisted_mid_collection_skips_verification_hint() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    hint = next_bundle_hint(draft, assisted=True)
    assert "send_verification" not in hint
    assert "start verification" not in hint


def test_tenant_brands_hint_names_both_when_brand_empty() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "tenant"
    _set(draft, FieldKey.COMPANY_NAME, "Al Noor Retail Group")
    _set(draft, FieldKey.COMPANY_ADDRESS, "King Abdulaziz Road, Riyadh")
    _set(draft, FieldKey.MALLS, ["riyadh-mall-a"])
    _set(draft, FieldKey.UNIT_TYPE, "store", Source.USER)
    hint = next_bundle_hint(
        draft,
        tenant_brands=["Noor Fashion", "Noor Beauty"],
    )
    assert "Noor Fashion" in hint and "Noor Beauty" in hint
    assert "Next question (brand)" in hint


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


def _uploaded(draft):
    from datetime import UTC, datetime

    from app.domain.draft_ops import add_document
    from app.domain.models import DocType

    for doc_type, file_id in ((DocType.COMPANY_PROFILE, "co-1"), (DocType.BRAND_PROFILE, "br-1")):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=f"{file_id}.pdf",
            size_bytes=100,
            max_bytes=5 * 1024 * 1024,
            uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    return draft


def test_documents_before_the_email_link_still_name_the_link() -> None:
    # Nov 2026 manual test: documents uploaded and mobile verified, email link not opened;
    # the agent called it the last step. The hint must say what's still open.
    draft = _uploaded(_ready_for_verification())
    draft.email_link_sent_to = "sara@example.com"
    draft.otp_sent_to = "+966501234567"
    draft.mobile_verified = True
    hint = next_bundle_hint(draft)
    assert "Still needed before submit (any order): the email link" in hint
    assert "only the terms" not in hint
    assert "SMS code" not in hint.split("Still needed")[1]


def test_only_terms_left_points_to_the_review_card() -> None:
    draft = _uploaded(_ready_for_verification())
    draft.email_verified = True
    draft.mobile_verified = True
    hint = next_bundle_hint(draft)
    assert "only the terms" in hint
    assert "show_review" in hint


def test_a_missing_field_is_named_rather_than_only_the_terms() -> None:
    # Re-demo flow 3 (10 Nov): the Brand Profile filled the brand, the documents and contact
    # were done, the Arabic name was missing; the hint said "only the terms", so the agent
    # kept pointing to a review card that couldn't show.
    draft = _uploaded(_ready_for_verification())
    draft.email_verified = True
    draft.mobile_verified = True
    draft.fields[FieldKey.BRAND_NAME_AR] = FieldValue()
    hint = next_bundle_hint(draft)
    still_needed = hint.split("Still needed before submit")[1]
    assert "only the terms" not in still_needed
    assert "Brand name (AR) (ask in chat)" in still_needed


def test_an_unconfirmed_value_is_named_in_the_still_needed_line() -> None:
    draft = _uploaded(_ready_for_verification())
    draft.email_verified = True
    draft.mobile_verified = True
    draft.fields[FieldKey.UNIT_TYPE] = FieldValue(value="specialty", source=Source.DERIVED)
    still_needed = next_bundle_hint(draft).split("Still needed before submit")[1]
    assert "confirming Unit type" in still_needed
