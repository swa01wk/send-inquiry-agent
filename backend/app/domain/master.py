"""Load and query seeded master data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class MasterItem(BaseModel):
    id: str
    label: str


class UnitType(MasterItem):
    code: str


class Mall(BaseModel):
    id: str
    name: str
    city: str


class MasterData(BaseModel):
    unit_types: list[UnitType] = Field(default_factory=list)
    sales_categories: list[MasterItem] = Field(default_factory=list)
    cities: list[MasterItem] = Field(default_factory=list)
    malls: list[Mall] = Field(default_factory=list)
    lease_periods: list[MasterItem] = Field(default_factory=list)
    rent_periods: list[MasterItem] = Field(default_factory=list)

    def label_for(self, kind: str, item_id: str) -> str | None:
        if kind not in {
            "unit_types",
            "sales_categories",
            "cities",
            "malls",
            "lease_periods",
            "rent_periods",
        }:
            raise KeyError(kind)
        if kind == "malls":
            for mall in self.malls:
                if mall.id == item_id:
                    return mall.name
        items = self._items_for_kind(kind)
        for item in items:
            if item.id == item_id:
                if isinstance(item, MasterItem):
                    return item.label
        return None

    def malls_in_city(self, city_id: str) -> list[Mall]:
        return [mall for mall in self.malls if mall.city == city_id]

    def unit_code(self, unit_type_id: str) -> str | None:
        for unit in self.unit_types:
            if unit.id == unit_type_id:
                return unit.code
        return None

    def mall_ids(self) -> set[str]:
        return {mall.id for mall in self.malls}

    def ids_for_kind(self, kind: str) -> set[str]:
        return {item.id for item in self._items_for_kind(kind)}

    def _items_for_kind(self, kind: str) -> list[MasterItem | Mall]:
        mapping: dict[str, list[MasterItem | Mall]] = {
            "unit_types": list(self.unit_types),
            "sales_categories": list(self.sales_categories),
            "cities": list(self.cities),
            "malls": list(self.malls),
            "lease_periods": list(self.lease_periods),
            "rent_periods": list(self.rent_periods),
        }
        if kind not in mapping:
            msg = f"Unknown master kind: {kind}"
            raise KeyError(msg)
        return mapping[kind]


_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "master_data.json"


@lru_cache
def load_master_data() -> MasterData:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return MasterData.model_validate(raw)
