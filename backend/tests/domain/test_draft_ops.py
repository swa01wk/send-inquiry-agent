from datetime import UTC, datetime

from app.domain.draft_ops import add_document, confirm, new_inquiry_draft, write_fields
from app.domain.models import DocType, FieldKey, Source


def test_write_same_value_keeps_verified_source(master):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.VERIFIED)],
        master=master,
    )
    draft, written, errors = write_fields(
        draft,
        [(FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.DERIVED)],
        master=master,
    )
    assert not errors
    assert written == []
    assert draft.fields[FieldKey.COMPANY_NAME].source == Source.VERIFIED
    assert draft.fields[FieldKey.COMPANY_NAME].confirmed is False


def test_write_fields_provenance_and_contact(master):
    draft = new_inquiry_draft()
    draft, written, errors = write_fields(
        draft,
        [
            ("company_name", "Bean Street Trading Co.", Source.DERIVED),
            ("contact_number", "0501234567", Source.USER),
        ],
        master=master,
    )
    assert not errors
    assert "company_name" in written
    assert draft.fields[FieldKey.COMPANY_NAME].confirmed is False
    assert draft.fields[FieldKey.MOBILE].value == "+966501234567"
    assert draft.fields[FieldKey.MOBILE].confirmed is True

    draft = confirm(draft, ["company_name"])
    assert draft.fields[FieldKey.COMPANY_NAME].confirmed is True


def test_defaults_on_new_draft():
    draft = new_inquiry_draft()
    assert draft.fields[FieldKey.AREA_MIN].value == 10
    assert draft.fields[FieldKey.AREA_MAX].value == 25000
    assert draft.fields[FieldKey.AREA_MIN].source == Source.DEFAULT
    assert draft.fields[FieldKey.AREA_MIN].confirmed is True


def test_add_document_validation():
    draft = new_inquiry_draft()
    updated, err = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="f1",
        file_name="profile.exe",
        size_bytes=100,
        max_bytes=5 * 1024 * 1024,
        uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert err is not None
    assert err.code == "invalid_extension"
    updated, err = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="f1",
        file_name="profile.pdf",
        size_bytes=100,
        max_bytes=5 * 1024 * 1024,
        uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert err is None
    assert DocType.COMPANY_PROFILE in updated.documents


def test_changing_email_or_mobile_clears_its_verification(master):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            ("email", "sara@beanstreet.example", Source.USER),
            ("contact_number", "0501234567", Source.USER),
        ],
        master=master,
    )
    draft.email_verified = True
    draft.mobile_verified = True
    draft.email_link_sent_to = "sara@beanstreet.example"
    draft.otp_sent_to = "+966501234567"

    # Re-writing the same values keeps verification.
    same, _, _ = write_fields(
        draft, [("email", "sara@beanstreet.example", Source.USER)], master=master
    )
    assert same.email_verified

    changed, _, _ = write_fields(
        draft, [("email", "sara@other.example", Source.USER)], master=master
    )
    assert not changed.email_verified
    assert changed.email_link_sent_to is None
    assert changed.mobile_verified

    changed, _, _ = write_fields(
        draft, [("contact_number", "0559876543", Source.USER)], master=master
    )
    assert not changed.mobile_verified
    assert changed.otp_sent_to is None
    assert changed.email_verified
