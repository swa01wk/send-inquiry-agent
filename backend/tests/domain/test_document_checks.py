"""Typed values against the profiles (demo feedback §3.7, D12)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.domain.document_checks import category_id, document_mismatches, normalise_for_compare
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import (
    DocType,
    DocumentRef,
    DocumentReview,
    ExtractedValue,
    FieldKey,
    InquiryDraft,
    Source,
)

MASTER = load_master_data()
T0 = datetime(2026, 11, 9, 9, 0, tzinfo=UTC)


def _with_profile(
    draft: InquiryDraft,
    doc_type: DocType,
    fields: dict[str, str],
    *,
    status: str = "done",
    filled: list[str] | None = None,
) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    updated.documents[doc_type] = DocumentRef(
        doc_type=doc_type,
        file_id=f"{doc_type.value}-1",
        file_name=f"{doc_type.value}.pdf",
        size_bytes=100,
        uploaded_at=T0,
        review=DocumentReview(
            status=status,  # type: ignore[arg-type]
            fields={k: ExtractedValue(value=v) for k, v in fields.items()},
            checked_at=T0,
        ),
        filled_fields=filled or [],
    )
    return updated


def _typed(**values: str) -> InquiryDraft:
    draft, _written, errors = write_fields(
        new_inquiry_draft(),
        [(key, value, Source.USER) for key, value in values.items()],
        master=MASTER,
    )
    assert not errors, errors
    return draft


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Bean Street Trading Co.", "bean street trading co"),
        ("King Fahd Road, Al Olaya, Riyadh", "King Fahd Road Al-Olaya Riyadh"),
        ("شركة الواحة للتجارة", "شركه الواحه للتجاره"),  # ta marbuta
        ("أحمد", "احمد"),  # alef with hamza
        ("مُحَمَّد", "محمد"),  # diacritics
        ("Unit ١٢", "unit 12"),  # Arabic-Indic digits
    ],
)
def test_normalise_ignores_case_spacing_punctuation_and_arabic_forms(a: str, b: str) -> None:
    assert normalise_for_compare(a) == normalise_for_compare(b)


def test_normalise_keeps_different_words_different() -> None:
    assert normalise_for_compare("Bean Street Trading Co.") != normalise_for_compare(
        "Bean Street Holding Company"
    )


def test_category_by_id_english_or_arabic_label() -> None:
    assert category_id("fnb_cafe", MASTER) == "fnb_cafe"
    assert category_id("Food & Beverage · Café", MASTER) == "fnb_cafe"
    assert category_id("أغذية ومشروبات · مقهى", MASTER) == "fnb_cafe"


def test_matching_typed_values_give_no_flag() -> None:
    draft = _typed(company_name="Bean Street Trading Co")
    draft = _with_profile(
        draft, DocType.COMPANY_PROFILE, {"company_name": "BEAN STREET TRADING CO."}
    )
    assert document_mismatches(draft, MASTER) == []


def test_a_different_typed_value_is_flagged_with_both_values() -> None:
    draft = _typed(company_name="Bean Street Trading Co.")
    draft = _with_profile(
        draft, DocType.COMPANY_PROFILE, {"company_name": "Bean Street Holding Company"}
    )
    [mismatch] = document_mismatches(draft, MASTER)
    assert mismatch.field == "company_name"
    assert mismatch.typed == "Bean Street Trading Co."
    assert mismatch.document_value == "Bean Street Holding Company"
    assert mismatch.doc_type == "company_profile"
    assert mismatch.doc_label == "Company Profile"


def test_category_compares_ids_and_shows_labels() -> None:
    draft = _typed(sales_category="fashion")
    draft = _with_profile(draft, DocType.BRAND_PROFILE, {"sales_category": "fnb_cafe"})
    [mismatch] = document_mismatches(draft, MASTER)
    assert mismatch.typed == "Fashion & Apparel"
    assert mismatch.document_value == "Food & Beverage · Café"

    same = _with_profile(
        _typed(sales_category="fnb_cafe"),
        DocType.BRAND_PROFILE,
        {"sales_category": "Food & Beverage · Café"},
    )
    assert document_mismatches(same, MASTER) == []


def test_a_corrected_value_stops_being_flagged() -> None:
    draft = _with_profile(
        _typed(company_name="Bean Street Trading Co."),
        DocType.COMPANY_PROFILE,
        {"company_name": "Bean Street Holding Company"},
    )
    assert document_mismatches(draft, MASTER)
    corrected, _w, _e = write_fields(
        draft, [("company_name", "Bean Street Holding Company", Source.USER)], master=MASTER
    )
    assert document_mismatches(corrected, MASTER) == []


def test_empty_fields_values_from_the_same_document_and_unread_documents_are_skipped() -> None:
    empty = _with_profile(new_inquiry_draft(), DocType.COMPANY_PROFILE, {"company_name": "X"})
    assert document_mismatches(empty, MASTER) == []

    filled, _w, _e = write_fields(
        new_inquiry_draft(),
        [("company_name", "From The Profile", Source.DERIVED)],
        master=MASTER,
        evidence={"company_name": "Company Profile: company_profile.pdf"},
    )
    own = _with_profile(
        filled,
        DocType.COMPANY_PROFILE,
        {"company_name": "Something else"},
        filled=["company_name"],
    )
    assert document_mismatches(own, MASTER) == []

    pending = _with_profile(
        _typed(company_name="Typed"),
        DocType.COMPANY_PROFILE,
        {"company_name": "Other"},
        status="pending",
    )
    assert document_mismatches(pending, MASTER) == []


def test_filter_by_doc_type() -> None:
    draft = _typed(company_name="Typed Co", brand_name_en="Typed Brand")
    draft = _with_profile(draft, DocType.COMPANY_PROFILE, {"company_name": "Doc Co"})
    draft = _with_profile(draft, DocType.BRAND_PROFILE, {"brand_name_en": "Doc Brand"})
    assert {m.field for m in document_mismatches(draft, MASTER)} == {
        "company_name",
        "brand_name_en",
    }
    only_brand = document_mismatches(draft, MASTER, doc_type=DocType.BRAND_PROFILE)
    assert [m.field for m in only_brand] == ["brand_name_en"]
    assert FieldKey.BRAND_NAME_EN.value == "brand_name_en"
