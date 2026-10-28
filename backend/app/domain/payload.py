"""The lead sent to Yardi on final approval (L4 §3.7)."""

from __future__ import annotations

from typing import Any

from app.domain.master import MasterData
from app.domain.models import FieldKey
from app.workflow.models import Case


def lead_payload(case: Case, master: MasterData) -> dict[str, Any]:
    """Customer, brand (re-linked Yardi ids when set), contacts, sales data and documents."""
    fields = case.draft.fields

    def value(key: FieldKey) -> Any:
        return fields[key].value

    malls = value(FieldKey.MALLS) or []
    return {
        "reference": case.reference,
        "customer": {
            "yardi_company_id": case.yardi.company_id,
            "name": value(FieldKey.COMPANY_NAME),
            "cr_number": value(FieldKey.CR_NUMBER),
            "address": value(FieldKey.COMPANY_ADDRESS),
        },
        "brand": {
            "yardi_brand_id": case.yardi.brand_id,
            "name_en": value(FieldKey.BRAND_NAME_EN),
            "name_ar": value(FieldKey.BRAND_NAME_AR),
        },
        "space": {
            "unit_type": value(FieldKey.UNIT_TYPE),
            "sales_category": value(FieldKey.SALES_CATEGORY),
            "malls": [master.label_for("malls", m) or m for m in malls],
            "area_min": value(FieldKey.AREA_MIN),
            "area_max": value(FieldKey.AREA_MAX),
        },
        "primary_contact": {
            "first_name": value(FieldKey.FIRST_NAME),
            "last_name": value(FieldKey.LAST_NAME),
            "email": value(FieldKey.EMAIL),
            "mobile": value(FieldKey.MOBILE),
            "landline": value(FieldKey.LANDLINE),
        },
        "tenant_contacts": [
            {
                "role": c.role,
                "first_name": c.first_name.value,
                "last_name": c.last_name.value,
                "email": c.email.value,
                "mobile": c.mobile.value,
                "landline": c.landline.value,
            }
            for c in case.tenant_contacts
        ],
        "sales_data": case.sales_data.file_id if case.sales_data else None,
        "documents": {d.value: ref.file_id for d, ref in case.draft.documents.items()},
    }
