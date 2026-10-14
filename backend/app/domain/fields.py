"""Field registry: labels, groups, required flags, and validation hooks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.domain import validation as v
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey, InquiryDraft


class FieldGroup(StrEnum):
    COMPANY = "company"
    BRAND = "brand"
    SPACE = "space"
    CONTACT = "contact"
    DOCUMENTS = "documents"


@dataclass(frozen=True)
class FieldDefinition:
    key: FieldKey
    label: str
    group: FieldGroup
    required: bool
    validator: Callable[[Any, MasterData], Any | v.ValidationError]
    display: Callable[[InquiryDraft, MasterData], str | None]


def _optional_str(raw: Any, _master: MasterData) -> str | v.ValidationError:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return ""
    if not isinstance(raw, str):
        return v.ValidationError(code="invalid_value", message="Expected text.")
    return raw.strip()


def _display_str(draft: InquiryDraft, key: FieldKey) -> str | None:
    val = draft.fields[key].value
    if val is None or val == "":
        return None
    return str(val)


def _make_master_validator(kind: str, code: str, label: str) -> Callable[[Any, MasterData], Any]:
    def _validate(raw: Any, master: MasterData) -> str | v.ValidationError:
        if not isinstance(raw, str):
            return v.ValidationError(code=code, message=f"Invalid {label}.")
        return v.validate_master_id(raw, kind=kind, master=master, code=code, label=label)

    return _validate


FIELD_DEFINITIONS: list[FieldDefinition] = [
    FieldDefinition(
        FieldKey.CR_NUMBER,
        "CR number",
        FieldGroup.COMPANY,
        False,
        lambda raw, _m: v.validate_cr_number(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.CR_NUMBER),
    ),
    FieldDefinition(
        FieldKey.COMPANY_NAME,
        "Company name",
        FieldGroup.COMPANY,
        True,
        lambda raw, _m: v.validate_company_name(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.COMPANY_NAME),
    ),
    FieldDefinition(
        FieldKey.COMPANY_ADDRESS,
        "Company address",
        FieldGroup.COMPANY,
        True,
        lambda raw, _m: v.validate_company_address(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.COMPANY_ADDRESS),
    ),
    FieldDefinition(
        FieldKey.BRAND_NAME_EN,
        "Brand name (EN)",
        FieldGroup.BRAND,
        True,
        lambda raw, _m: v.validate_brand_name_en(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.BRAND_NAME_EN),
    ),
    FieldDefinition(
        FieldKey.BRAND_NAME_AR,
        "Brand name (AR)",
        FieldGroup.BRAND,
        True,
        lambda raw, _m: v.validate_brand_name_ar(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.BRAND_NAME_AR),
    ),
    FieldDefinition(
        FieldKey.UNIT_TYPE,
        "Unit type",
        FieldGroup.BRAND,
        True,
        _make_master_validator("unit_types", "invalid_unit_type", "unit type"),
        lambda d, m: (
            m.label_for("unit_types", str(d.fields[FieldKey.UNIT_TYPE].value or ""))
            or _display_str(d, FieldKey.UNIT_TYPE)
        ),
    ),
    FieldDefinition(
        FieldKey.SALES_CATEGORY,
        "Sales category",
        FieldGroup.BRAND,
        True,
        _make_master_validator("sales_categories", "invalid_sales_category", "sales category"),
        lambda d, m: (
            m.label_for("sales_categories", str(d.fields[FieldKey.SALES_CATEGORY].value or ""))
            or _display_str(d, FieldKey.SALES_CATEGORY)
        ),
    ),
    FieldDefinition(
        FieldKey.MALLS,
        "Malls",
        FieldGroup.SPACE,
        True,
        lambda raw, master: v.validate_malls(raw, master),
        lambda d, m: (
            ", ".join(
                m.label_for("malls", mall_id) or mall_id
                for mall_id in (d.fields[FieldKey.MALLS].value or [])
            )
            or None
        ),
    ),
    FieldDefinition(
        FieldKey.AREA_MIN,
        "Area min (sqm)",
        FieldGroup.SPACE,
        False,
        lambda raw, _m: v.validate_area_min(raw),
        lambda d, _m: _display_str(d, FieldKey.AREA_MIN),
    ),
    FieldDefinition(
        FieldKey.AREA_MAX,
        "Area max (sqm)",
        FieldGroup.SPACE,
        False,
        lambda raw, _m: v.validate_area_max(raw),
        lambda d, _m: _display_str(d, FieldKey.AREA_MAX),
    ),
    FieldDefinition(
        FieldKey.RENT_PERIOD,
        "Rent period",
        FieldGroup.SPACE,
        False,
        _make_master_validator("rent_periods", "invalid_rent_period", "rent period"),
        lambda d, m: (
            m.label_for("rent_periods", str(d.fields[FieldKey.RENT_PERIOD].value or ""))
            or _display_str(d, FieldKey.RENT_PERIOD)
        ),
    ),
    FieldDefinition(
        FieldKey.RENT_MIN,
        "Rent min (SAR)",
        FieldGroup.SPACE,
        False,
        lambda raw, _m: v.validate_rent_min(raw),
        lambda d, _m: _display_str(d, FieldKey.RENT_MIN),
    ),
    FieldDefinition(
        FieldKey.RENT_MAX,
        "Rent max (SAR)",
        FieldGroup.SPACE,
        False,
        lambda raw, _m: v.validate_rent_max(raw),
        lambda d, _m: _display_str(d, FieldKey.RENT_MAX),
    ),
    FieldDefinition(
        FieldKey.LEASE_PERIOD,
        "Lease period",
        FieldGroup.SPACE,
        False,
        _make_master_validator("lease_periods", "invalid_lease_period", "lease period"),
        lambda d, m: (
            m.label_for("lease_periods", str(d.fields[FieldKey.LEASE_PERIOD].value or ""))
            or _display_str(d, FieldKey.LEASE_PERIOD)
        ),
    ),
    FieldDefinition(
        FieldKey.FIRST_NAME,
        "First name",
        FieldGroup.CONTACT,
        True,
        lambda raw, _m: v.validate_name(str(raw), code="invalid_first_name", label="First name"),
        lambda d, _m: _display_str(d, FieldKey.FIRST_NAME),
    ),
    FieldDefinition(
        FieldKey.LAST_NAME,
        "Last name",
        FieldGroup.CONTACT,
        True,
        lambda raw, _m: v.validate_name(str(raw), code="invalid_last_name", label="Last name"),
        lambda d, _m: _display_str(d, FieldKey.LAST_NAME),
    ),
    FieldDefinition(
        FieldKey.EMAIL,
        "Email",
        FieldGroup.CONTACT,
        True,
        lambda raw, _m: v.validate_email(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.EMAIL),
    ),
    FieldDefinition(
        FieldKey.MOBILE,
        "Mobile",
        FieldGroup.CONTACT,
        False,
        lambda raw, _m: v.normalise_saudi_mobile(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.MOBILE),
    ),
    FieldDefinition(
        FieldKey.LANDLINE,
        "Office landline",
        FieldGroup.CONTACT,
        False,
        lambda raw, _m: v.normalise_saudi_landline(str(raw)),
        lambda d, _m: _display_str(d, FieldKey.LANDLINE),
    ),
    FieldDefinition(
        FieldKey.VAT_NUMBER,
        "VAT number",
        FieldGroup.DOCUMENTS,
        False,
        lambda raw, _m: v.validate_vat_number(str(raw)) if str(raw).strip() else "",
        lambda d, _m: _display_str(d, FieldKey.VAT_NUMBER),
    ),
    FieldDefinition(
        FieldKey.NATIONAL_ID_NUMBER,
        "National ID / Iqama",
        FieldGroup.DOCUMENTS,
        False,
        lambda raw, _m: v.validate_national_id_number(str(raw)) if str(raw).strip() else "",
        lambda d, _m: _display_str(d, FieldKey.NATIONAL_ID_NUMBER),
    ),
    FieldDefinition(
        FieldKey.NATIONAL_ADDRESS,
        "National address",
        FieldGroup.DOCUMENTS,
        False,
        lambda raw, _m: v.validate_national_address(str(raw)) if str(raw).strip() else "",
        lambda d, _m: _display_str(d, FieldKey.NATIONAL_ADDRESS),
    ),
]

FIELD_BY_KEY: dict[FieldKey, FieldDefinition] = {f.key: f for f in FIELD_DEFINITIONS}

GROUP_ORDER: list[FieldGroup] = [
    FieldGroup.COMPANY,
    FieldGroup.BRAND,
    FieldGroup.SPACE,
    FieldGroup.CONTACT,
]

DOCUMENT_DEFINITIONS: list[tuple[DocType, str, bool]] = [
    (DocType.COMPANY_PROFILE, "Company Profile", True),
    (DocType.BRAND_PROFILE, "Brand Profile", True),
    (DocType.CR_CERTIFICATE, "CR certificate", False),
    (DocType.VAT_CERTIFICATE, "VAT certificate", False),
    (DocType.NATIONAL_ID, "National ID / Iqama", False),
    (DocType.NATIONAL_ADDRESS, "National Address", False),
    (DocType.ARTICLES_OF_ASSOCIATION, "Article of Association", False),
]


def display_area(draft: InquiryDraft) -> str | None:
    area_min = draft.fields[FieldKey.AREA_MIN].value
    area_max = draft.fields[FieldKey.AREA_MAX].value
    if area_min is None and area_max is None:
        return None
    lo = area_min if area_min is not None else area_max
    hi = area_max if area_max is not None else area_min
    if lo == hi:
        return f"{lo} sqm"
    return f"{lo} – {hi} sqm"


def display_rent(draft: InquiryDraft, master: MasterData) -> str | None:
    rent_min = draft.fields[FieldKey.RENT_MIN].value
    rent_max = draft.fields[FieldKey.RENT_MAX].value
    if rent_min is None and rent_max is None:
        return None
    period_id = draft.fields[FieldKey.RENT_PERIOD].value
    period = master.label_for("rent_periods", str(period_id)) if period_id else None
    suffix = f" / {period.lower()}" if period else ""

    def fmt(amount: int) -> str:
        return f"SAR {amount:,}"

    if rent_min is not None and rent_max is not None:
        if rent_min == rent_max:
            text = fmt(rent_min)
        else:
            text = f"{fmt(rent_min)} – {fmt(rent_max)}"
    elif rent_max is not None:
        text = f"Up to {fmt(rent_max)}"
    elif rent_min is not None:
        text = f"From {fmt(rent_min)}"
    else:
        return None
    return f"{text}{suffix}"


def display_lease(draft: InquiryDraft, master: MasterData) -> str | None:
    lease_id = draft.fields[FieldKey.LEASE_PERIOD].value
    if not lease_id:
        return None
    return master.label_for("lease_periods", str(lease_id))
