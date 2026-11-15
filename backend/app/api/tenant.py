"""Tenant Central, simulated: mock sign-in and Leasing Opportunities, where a registered
company lands after "Customer already registered. Please login" (chart S3, M13). Raising an
inquiry from Tenant Central (R4) was removed with flow v2: it isn't on the chart.

Mounted only with `TENANT_PORTAL=true` and mock integrations. The frontend sends
`X-Tenant-Id` (in production, the Azure AD session).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from app.api.deps import get_master_data, get_services
from app.api.errors import ApiError
from app.domain.master import MasterData
from app.services.container import ServiceContainer
from app.services.tenants import Tenant

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


def current_tenant(
    x_tenant_id: str | None = Header(default=None),
    services: ServiceContainer = Depends(get_services),
) -> Tenant:
    tenant = services.tenants.get_by_id(x_tenant_id or "")
    if tenant is None:
        raise ApiError(401, "unknown_tenant", "Sign in to Tenant Central first.")
    return tenant


class TenantBrandOut(BaseModel):
    id: str
    name: str


class TenantOut(BaseModel):
    id: str
    company_name: str
    contact_name: str
    brands: list[TenantBrandOut]


class OpportunityOut(BaseModel):
    id: str
    mall_id: str
    mall: str
    city_id: str
    city: str
    unit_type: str
    unit_type_label: str
    unit_ref: str
    area_min: int
    area_max: int


def _tenant_out(tenant: Tenant) -> TenantOut:
    contact = tenant.primary_contact
    return TenantOut(
        id=tenant.id,
        company_name=tenant.company_name,
        contact_name=f"{contact.first_name} {contact.last_name}",
        brands=[TenantBrandOut(id=b.id, name=b.name_en) for b in tenant.brands],
    )


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(services: ServiceContainer = Depends(get_services)) -> list[TenantOut]:
    """For the mock sign-in picker."""
    return [_tenant_out(t) for t in services.tenants.all()]


@router.get("/me", response_model=TenantOut)
async def me(tenant: Tenant = Depends(current_tenant)) -> TenantOut:
    return _tenant_out(tenant)


def _opportunity_out(opportunity, master: MasterData) -> OpportunityOut:  # type: ignore[no-untyped-def]
    mall = next(m for m in master.malls if m.id == opportunity.mall)
    return OpportunityOut(
        id=opportunity.id,
        mall_id=mall.id,
        mall=mall.name,
        city_id=mall.city,
        city=master.label_for("cities", mall.city) or mall.city,
        unit_type=opportunity.unit_type,
        unit_type_label=master.label_for("unit_types", opportunity.unit_type)
        or opportunity.unit_type,
        unit_ref=opportunity.unit_ref,
        area_min=opportunity.area_min,
        area_max=opportunity.area_max,
    )


@router.get("/opportunities", response_model=list[OpportunityOut])
async def list_opportunities(
    city: str | None = Query(default=None),
    unit_type: str | None = Query(default=None),
    _tenant: Tenant = Depends(current_tenant),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
) -> list[OpportunityOut]:
    items = [_opportunity_out(o, master) for o in services.opportunities.all()]
    return [
        o
        for o in items
        if (city is None or o.city_id == city) and (unit_type is None or o.unit_type == unit_type)
    ]
