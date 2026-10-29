"""Prefill an inquiry from a Tenant Central record (intake channels §3.4).

One rule for every channel (call centre "continue for them", Leasing Opportunities, and
the public page under `allow_inquiry`): company, CR, VAT, National Address, the chosen
brand, its sales category and the primary contact are written as `verified`, unconfirmed,
for the applicant to confirm. With several brands and none chosen, the brand is left for
the agent to ask about.
"""

from __future__ import annotations

from app.domain import draft_ops
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft, Source, WriteKey
from app.services.tenants import Tenant

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
    brand = tenant.brand(brand_id)
    if brand is not None:
        entries.append((FieldKey.BRAND_NAME_EN.value, brand.name_en, Source.VERIFIED))
        if brand.name_ar:
            entries.append((FieldKey.BRAND_NAME_AR.value, brand.name_ar, Source.VERIFIED))
        if brand.sales_category:
            entries.append((FieldKey.SALES_CATEGORY.value, brand.sales_category, Source.VERIFIED))
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
    return updated, written
