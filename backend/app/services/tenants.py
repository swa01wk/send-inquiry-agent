"""Tenant Central records and Leasing Opportunities, simulated (intake channels §3.4–3.5).

`TenantDirectory` answers "who is this existing tenant?" by CR or id; `OpportunityCatalogue`
lists the units shown on Leasing Opportunities. Both read `data/mock_world/` until Cenomi
gives access to Tenant Central.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

MOCK_WORLD = Path(__file__).resolve().parent.parent / "data" / "mock_world"


class TenantBrand(BaseModel):
    id: str
    name_en: str
    name_ar: str | None = None
    sales_category: str | None = None


class TenantPerson(BaseModel):
    first_name: str
    last_name: str
    email: str
    mobile: str | None = None
    has_account: bool = False


class TenantRoleContact(TenantPerson):
    role: str


class TenantDocument(BaseModel):
    doc_type: str
    file_name: str


class TenantLease(BaseModel):
    mall: str
    unit_type: str


class Tenant(BaseModel):
    id: str
    cr_number: str
    company_name: str
    company_address: str
    vat_number: str | None = None
    national_address: str | None = None
    brands: list[TenantBrand]
    primary_contact: TenantPerson
    contacts: list[TenantRoleContact] = []
    documents: list[TenantDocument] = []
    leases: list[TenantLease] = []

    def brand(self, brand_id: str | None) -> TenantBrand | None:
        if brand_id is None:
            return self.brands[0] if len(self.brands) == 1 else None
        return next((b for b in self.brands if b.id == brand_id), None)


class Opportunity(BaseModel):
    id: str
    mall: str
    unit_type: str
    unit_ref: str
    area_min: int
    area_max: int


class TenantDirectory:
    def __init__(self, path: Path = MOCK_WORLD / "tenants.json") -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._tenants = [Tenant.model_validate(t) for t in raw["tenants"]]

    def all(self) -> list[Tenant]:
        return list(self._tenants)

    def get_by_id(self, tenant_id: str) -> Tenant | None:
        return next((t for t in self._tenants if t.id == tenant_id), None)

    def get_by_cr(self, cr_number: str) -> Tenant | None:
        return next((t for t in self._tenants if t.cr_number == cr_number.strip()), None)


class OpportunityCatalogue:
    def __init__(self, path: Path = MOCK_WORLD / "opportunities.json") -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self._items = [Opportunity.model_validate(o) for o in raw["opportunities"]]

    def all(self) -> list[Opportunity]:
        return list(self._items)

    def get(self, opportunity_id: str) -> Opportunity | None:
        return next((o for o in self._items if o.id == opportunity_id), None)
