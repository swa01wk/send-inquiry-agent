"""Tenant Central, simulated (intake channels §3.5): mock sign-in, Leasing Opportunities,
"Raise inquiry" in existing-tenant mode, and My inquiries.

Mounted only with `TENANT_PORTAL=true` and mock integrations. The frontend sends
`X-Tenant-Id` (in production, the Azure AD session).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from app.agent.actions import tracking_url
from app.agent.channels import attach_documents_on_file
from app.agent.runtime import AgentRuntime
from app.api.channel_cards import build_basic_info_card
from app.api.deps import get_master_data, get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.api.schemas import AssistantMessage, CreateSessionResponse
from app.config import Settings
from app.domain import draft_ops
from app.domain.case_brief import STAGE_LABELS
from app.domain.master import MasterData
from app.domain.models import FieldKey, Source
from app.domain.summary import build_draft_summary
from app.domain.tenant_prefill import prefill_from_tenant
from app.policy.config import get_policy
from app.services.container import ServiceContainer
from app.services.tenants import Tenant
from app.sessions import SessionStore

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


class RaiseInquiryBody(BaseModel):
    brand_id: str | None = None


class MyInquiryOut(BaseModel):
    reference: str
    brand: str | None
    mall: str | None
    product_line: str | None
    stage_label: str
    submitted_at: datetime
    last_change: datetime
    tracking_url: str


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


@router.post("/opportunities/{opportunity_id}/inquiry", response_model=CreateSessionResponse)
async def raise_inquiry(
    opportunity_id: str,
    body: RaiseInquiryBody,
    tenant: Tenant = Depends(current_tenant),
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> CreateSessionResponse:
    """Existing-tenant mode: prefilled from the tenant record, the property already chosen,
    verified by the sign-in, documents on file attached (intake channels §3.5)."""
    opportunity = services.opportunities.get(opportunity_id)
    if opportunity is None:
        raise ApiError(404, "opportunity_not_found", "That opportunity isn't listed any more.")
    if body.brand_id is not None and tenant.brand(body.brand_id) is None:
        raise ApiError(400, "unknown_brand", "That brand isn't on your account.")
    session = await store.create(
        channel="existing_tenant", created_by=tenant.id, tenant_id=tenant.id
    )
    draft, written = prefill_from_tenant(session.draft, tenant, master, brand_id=body.brand_id)
    draft, chosen, _errors = draft_ops.write_fields(
        draft,
        [
            (FieldKey.MALLS.value, [opportunity.mall], Source.USER),
            (FieldKey.UNIT_TYPE.value, opportunity.unit_type, Source.USER),
            (FieldKey.AREA_MIN.value, opportunity.area_min, Source.DEFAULT),
            (FieldKey.AREA_MAX.value, opportunity.area_max, Source.DEFAULT),
        ],
        master=master,
    )
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    if get_policy().signed_in_skips_verification:
        draft.email_verified = True
        draft.mobile_verified = True
        draft_ops.stamp_verified(draft)
        for channel in ("email", "mobile"):
            services.audit.record(
                session.id,
                "verification_result",
                actor="system",
                payload={"channel": channel, "result": "signed_in"},
            )
    draft, documents = attach_documents_on_file(runtime, session.id, draft, tenant)
    session.draft = draft
    services.audit.record(
        session.id, "inquiry_created", actor="user", payload={"channel": "existing_tenant"}
    )
    services.audit.record(
        session.id,
        "tenant_prefill",
        actor="system",
        payload={
            "tenant_id": tenant.id,
            "channel": "existing_tenant",
            "keys": [*written, *chosen],
            "documents": documents,
        },
    )

    mall = master.label_for("malls", opportunity.mall) or opportunity.mall
    greeting = (
        f"Welcome back, {tenant.primary_contact.first_name}. I've filled in "
        f"{tenant.company_name}'s details from your Tenant Central account for {mall} "
        f"(unit {opportunity.unit_ref}). Please check them and press Proceed."
    )
    if tenant.brand(body.brand_id) is None:
        names = " or ".join(b.name_en for b in tenant.brands)
        greeting += f" Which brand is this for — {names}? Or tell me if it's a new one."
    message = AssistantMessage(id="tenant-1", text=greeting)
    card = build_basic_info_card(
        draft, master, started_by="your Tenant Central account", message_id=message.id
    )
    session.add_message(message.id, "assistant", message.text)
    session.remember_card(card.model_dump())
    store.save(session)
    return CreateSessionResponse(
        session_id=session.id,
        messages=[message],
        cards=[card],
        draft=build_draft_summary(draft, master, changed_keys=[]),
    )


@router.get("/inquiries", response_model=list[MyInquiryOut])
async def my_inquiries(
    tenant: Tenant = Depends(current_tenant),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> list[MyInquiryOut]:
    """Every submitted inquiry for the tenant's company, newest first (§3.5)."""
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    rows: list[MyInquiryOut] = []
    for case in services.cases.all():
        if case.tenant_id != tenant.id:
            continue
        malls = case.draft.fields[FieldKey.MALLS].value or []
        unit_type = case.draft.fields[FieldKey.UNIT_TYPE].value
        rows.append(
            MyInquiryOut(
                reference=case.reference,
                brand=case.draft.fields[FieldKey.BRAND_NAME_EN].value,
                mall=master.label_for("malls", malls[0]) if malls else None,
                product_line=master.label_for("unit_types", unit_type) if unit_type else None,
                stage_label=STAGE_LABELS.get(case.status.value, case.status.value),
                submitted_at=case.submitted_at,
                last_change=case.last_change,
                tracking_url=tracking_url(runtime, case.session_id, case.reference),
            )
        )
    return sorted(rows, key=lambda r: r.submitted_at, reverse=True)
