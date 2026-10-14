"""Extra cases to cover validation, draft_ops, fields display, and master helpers."""

from datetime import UTC, datetime

import pytest
from app.domain import validation as v
from app.domain.draft_ops import add_document, new_inquiry_draft, remove_document, write_fields
from app.domain.fields import display_lease, display_rent
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey, Source


def test_validation_edge_cases():
    assert v.validate_area_max("bad").code == "invalid_area_max"
    assert v.validate_rent_min(-1).code == "invalid_rent_min"
    assert v.validate_rent_max("x").code == "invalid_rent_max"
    assert v.validate_name("", code="x", label="Name").code == "x"
    assert v.validate_company_name("x").code == "invalid_company_name"
    assert v.validate_national_address("tiny").code == "invalid_national_address"
    assert v.validate_malls("not-a-list", load_master_data()).code == "invalid_malls"
    assert v.normalise_saudi_mobile("bad").code == "invalid_mobile"
    assert v.normalise_saudi_landline("51234567").code == "invalid_landline"
    assert v.is_validation_error(v.ValidationError(code="a", message="b")) is True


def test_master_helpers():
    master = load_master_data()
    assert master.label_for("unit_types", "store") == "Store"
    assert master.label_for("malls", "riyadh-mall-a") == "Riyadh Mall A"
    assert master.label_for("unit_types", "missing") is None
    assert master.unit_code("store") == "STR"
    assert master.unit_code("nope") is None
    assert len(master.malls_in_city("riyadh")) == 4
    with pytest.raises(KeyError):
        master.label_for("nope", "x")


def test_write_fields_errors_and_clear_optional(master):
    draft = new_inquiry_draft()
    draft, _, errors = write_fields(
        draft,
        [("unknown_key", "x", Source.USER), ("vat_number", "", Source.USER)],
        master=master,
    )
    assert "unknown_key" in errors
    assert draft.fields[FieldKey.VAT_NUMBER].value is None

    draft, _, errors = write_fields(
        draft,
        [("rent_min", 1000, Source.USER), ("rent_max", 500, Source.USER)],
        master=master,
    )
    assert "rent" in errors

    draft, _, errors = write_fields(
        draft,
        [("area_min", 100, Source.USER), ("area_max", 50, Source.USER)],
        master=master,
    )
    assert "area" in errors


def test_display_rent_and_lease_variants(master):
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [
            ("rent_max", 250_000, Source.USER),
            ("rent_period", "yearly", Source.USER),
        ],
        master=master,
    )
    assert display_rent(draft, master) == "Up to SAR 250,000 / yearly"

    draft, _, _ = write_fields(
        draft,
        [("rent_min", 100_000, Source.USER), ("rent_max", 250_000, Source.USER)],
        master=master,
    )
    assert "100,000" in (display_rent(draft, master) or "")

    draft, _, _ = write_fields(draft, [("lease_period", "2y", Source.USER)], master=master)
    assert display_lease(draft, master) == "2 years"


def test_remove_document_and_invalid_source(master):
    draft = new_inquiry_draft()
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    draft, _ = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="1",
        file_name="co.pdf",
        size_bytes=10,
        max_bytes=5 * 1024 * 1024,
        uploaded_at=ts,
    )
    draft = remove_document(draft, DocType.COMPANY_PROFILE)
    assert DocType.COMPANY_PROFILE not in draft.documents

    draft, _, errors = write_fields(
        draft,
        [("company_name", "Bean Street Trading Co.", Source.USER)],
        master=master,
    )
    assert not errors
