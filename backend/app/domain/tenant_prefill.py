"""Prefill an inquiry from a Tenant Central record (intake channels §3.4).

One rule for every channel (call centre "continue for them", Leasing Opportunities, and
the public page under `allow_inquiry`): company, CR, VAT, National Address, the chosen
brand, its sales category and the primary contact are written as `verified`, unconfirmed,
for the applicant to confirm. With several brands and none chosen, the brand is left for
the agent to ask about.
"""

from __future__ import annotations

import re

from app.domain import draft_ops
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft, Source, WriteKey
from app.services.tenants import Tenant, TenantBrand

# The basic-info fields a tenant record can fill (shown on the basic_info_review card).
PREFILL_KEYS = (
    FieldKey.CR_NUMBER,
    FieldKey.COMPANY_NAME,
    FieldKey.COMPANY_ADDRESS,
    FieldKey.VAT_NUMBER,
    FieldKey.NATIONAL_ADDRESS,
    FieldKey.BRAND_NAME_EN,
    FieldKey.BRAND_NAME_AR,
    FieldKey.SALES_CATEGORY,
    FieldKey.FIRST_NAME,
    FieldKey.LAST_NAME,
    FieldKey.EMAIL,
    FieldKey.MOBILE,
)


def prefill_brand(
    draft: InquiryDraft,
    tenant: Tenant,
    master: MasterData,
    brand_id: str,
) -> tuple[InquiryDraft, list[str]]:
    """Write one tenant brand (English, Arabic, sales category) as verified, unconfirmed."""
    brand = tenant.brand(brand_id)
    if brand is None:
        return draft, []
    entries: list[tuple[str, object, Source]] = [
        (FieldKey.BRAND_NAME_EN.value, brand.name_en, Source.VERIFIED),
    ]
    if brand.name_ar:
        entries.append((FieldKey.BRAND_NAME_AR.value, brand.name_ar, Source.VERIFIED))
    if brand.sales_category:
        entries.append((FieldKey.SALES_CATEGORY.value, brand.sales_category, Source.VERIFIED))
    updated, written, _errors = draft_ops.write_fields(draft, entries, master=master)
    for key_str, value, _source in entries:
        key = FieldKey(key_str)
        field = updated.fields[key]
        if field.value == value and field.source != Source.VERIFIED:
            updated.fields[key] = field.model_copy(
                update={"source": Source.VERIFIED, "confirmed": False},
            )
            if key_str not in written:
                written.append(key_str)
    return updated, written


def _latin_brand_name_in_message(name: str, message: str) -> bool:
    pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
    return bool(re.search(pattern, message, re.IGNORECASE))


def tenant_brand_record_filled(draft: InquiryDraft, brand: TenantBrand) -> bool:
    """True when en, ar and sales_category on the draft match the tenant brand record."""
    en = draft.fields[FieldKey.BRAND_NAME_EN].value
    ar = draft.fields[FieldKey.BRAND_NAME_AR].value
    cat = draft.fields[FieldKey.SALES_CATEGORY].value
    if en != brand.name_en:
        return False
    if brand.name_ar is not None and ar != brand.name_ar:
        return False
    if brand.name_ar is None and ar:
        return False
    if brand.sales_category is not None and cat != brand.sales_category:
        return False
    if brand.sales_category is None and cat:
        return False
    return True


def apply_tenant_brand_pick_from_message(
    draft: InquiryDraft,
    tenant: Tenant,
    master: MasterData,
    message: str,
) -> tuple[InquiryDraft, list[str]]:
    """When the message names one account brand, prefill the full brand record if needed."""
    matched = match_single_brand_in_message(tenant, message)
    if matched is None or tenant_brand_record_filled(draft, matched):
        return draft, []
    return prefill_brand(draft, tenant, master, matched.id)


def match_single_brand_in_message(tenant: Tenant, message: str) -> TenantBrand | None:
    """When the message names exactly one brand on the account, return it."""
    matched: list[TenantBrand] = []
    for brand in tenant.brands:
        if brand.name_en and _latin_brand_name_in_message(brand.name_en, message):
            matched.append(brand)
        elif brand.name_ar and brand.name_ar in message:
            matched.append(brand)
    unique = {b.id: b for b in matched}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def prefill_from_tenant(
    draft: InquiryDraft,
    tenant: Tenant,
    master: MasterData,
    *,
    brand_id: str | None = None,
) -> tuple[InquiryDraft, list[str]]:
    """Returns the draft and the keys written. `cr_status` becomes "tenant"."""
    entries: list[tuple[str, object, Source]] = [
        (FieldKey.CR_NUMBER.value, tenant.cr_number, Source.VERIFIED),
        (FieldKey.COMPANY_NAME.value, tenant.company_name, Source.VERIFIED),
        (FieldKey.COMPANY_ADDRESS.value, tenant.company_address, Source.VERIFIED),
    ]
    if tenant.vat_number:
        entries.append((FieldKey.VAT_NUMBER.value, tenant.vat_number, Source.VERIFIED))
    if tenant.national_address:
        entries.append((FieldKey.NATIONAL_ADDRESS.value, tenant.national_address, Source.VERIFIED))
    contact = tenant.primary_contact
    entries += [
        (FieldKey.FIRST_NAME.value, contact.first_name, Source.VERIFIED),
        (FieldKey.LAST_NAME.value, contact.last_name, Source.VERIFIED),
        (FieldKey.EMAIL.value, contact.email, Source.VERIFIED),
    ]
    if contact.mobile:
        entries.append((WriteKey.CONTACT_NUMBER.value, contact.mobile, Source.VERIFIED))
    updated, written, _errors = draft_ops.write_fields(draft, entries, master=master)
    updated.cr_status = "tenant"
    brand = tenant.brand(brand_id)
    if brand is not None:
        updated, brand_written = prefill_brand(updated, tenant, master, brand.id)
        written = [*written, *brand_written]
    return updated, written
