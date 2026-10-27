"""Master data lookup endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_master_data
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import MallResponse, MasterItemResponse, UnitTypeResponse
from app.domain.master import MasterData
from app.policy.config import get_policy

router = APIRouter(prefix="/api/master", tags=["master"])

MasterListItem = MasterItemResponse | UnitTypeResponse | MallResponse


@router.get("/{kind}", response_model=list[MasterListItem])
@limiter.limit("60/minute")
async def get_master_kind(
    request: Request,
    kind: str,
    city: Annotated[str | None, Query()] = None,
    master: MasterData = Depends(get_master_data),
) -> list[MasterListItem]:
    if kind not in {
        "unit_types",
        "sales_categories",
        "cities",
        "malls",
        "lease_periods",
        "rent_periods",
    }:
        raise ApiError(
            400,
            "unknown_master_kind",
            "That master data type isn't available.",
        )

    if kind == "unit_types":
        lines = get_policy().product_lines
        return [
            UnitTypeResponse(id=item.id, label=item.label, code=item.code)
            for item in master.unit_types
            if item.id in lines
        ]
    if kind == "malls":
        malls = master.malls_in_city(city) if city else master.malls
        return [MallResponse(id=m.id, name=m.name, city=m.city) for m in malls]
    if kind == "cities":
        return [MasterItemResponse(id=item.id, label=item.label) for item in master.cities]
    if kind == "sales_categories":
        return [
            MasterItemResponse(id=item.id, label=item.label) for item in master.sales_categories
        ]
    if kind == "lease_periods":
        return [MasterItemResponse(id=item.id, label=item.label) for item in master.lease_periods]
    return [MasterItemResponse(id=item.id, label=item.label) for item in master.rent_periods]
