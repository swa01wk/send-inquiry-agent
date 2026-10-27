import json
from pathlib import Path

from app.domain.master import load_master_data


def test_no_office_unit_type_in_seed_data() -> None:
    master = load_master_data()
    ids = master.ids_for_kind("unit_types")
    assert "office" not in ids
    labels = [master.label_for("unit_types", uid) or "" for uid in ids]
    assert not any("office" in label.lower() for label in labels)


def test_faq_and_json_contain_no_office_product_line() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "data"
    master_raw = json.loads((root / "master_data.json").read_text())
    faq_raw = json.loads((root / "faq.json").read_text())
    blob = json.dumps(master_raw).lower()
    assert '"office"' not in blob
    assert "off" not in {u.get("code", "").lower() for u in master_raw["unit_types"]}
    faq_blob = json.dumps(faq_raw).lower()
    assert "office space" not in faq_blob


# ---- Generated master data (L3 §3.8) -------------------------------------------------

import importlib.util  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import pytest  # noqa: E402
from app.agent.mall_match import mentioned_seed_mall_ids  # noqa: E402
from app.domain.master import (  # noqa: E402
    CachedMasterData,
    CenomiMasterDataSource,
    MasterData,
    MasterDataUnavailable,
    SeedMasterDataSource,
)

_GENERATOR = Path(__file__).resolve().parents[2] / "scripts" / "generate_master_data.py"


def _generator():
    spec = importlib.util.spec_from_file_location("generate_master_data", _GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_is_deterministic_and_committed_file_is_current() -> None:
    generator = _generator()
    assert generator.render() == generator.render()
    assert generator.main(["--check"]) == 0


def test_existing_ids_are_kept() -> None:
    master = load_master_data()
    assert {
        "riyadh-mall-a",
        "riyadh-mall-b",
        "riyadh-mall-c",
        "riyadh-mall-d",
        "jeddah-mall-a",
        "jeddah-mall-b",
        "mall-of-arabia",
        "dammam-mall-a",
        "mall-of-dhahran",
    } <= master.mall_ids()
    assert {"riyadh", "jeddah", "dammam"} <= master.ids_for_kind("cities")
    assert master.ids_for_kind("sales_categories") == {
        "fnb_cafe",
        "fnb_restaurant",
        "fashion",
        "beauty",
        "electronics",
        "entertainment",
        "services",
    }
    assert [m.id for m in master.malls_in_city("riyadh")] == [
        "riyadh-mall-a",
        "riyadh-mall-b",
        "riyadh-mall-c",
        "riyadh-mall-d",
    ]


def test_every_mall_has_arabic_name_and_region_of_its_city() -> None:
    master = load_master_data()
    regions = {r.id for r in master.regions}
    assert regions == {"central", "western", "eastern"}
    city_region = {c.id: c.region for c in master.cities}
    assert 18 <= len(master.malls) <= 22
    for mall in master.malls:
        assert mall.name_ar, mall.id
        assert mall.region in regions, mall.id
        assert mall.region == city_region[mall.city], mall.id
    for kind in ("unit_types", "sales_categories", "lease_periods", "rent_periods"):
        assert all(item.label_ar for item in getattr(master, kind)), kind
    assert all(city.label_ar for city in master.cities)


@pytest.mark.parametrize(
    ("text", "mall_id"),
    [
        ("نبي محل في الرياض مول أ", "riyadh-mall-a"),
        ("في مول جدة ب لو سمحت", "jeddah-mall-b"),
        ("عندنا كشك في مول العرب", "mall-of-arabia"),
        ("الرياض مول ا", "riyadh-mall-a"),
        ("Khobar Mall C please", "khobar-mall-c"),
    ],
)
def test_arabic_and_new_mall_names_match_their_id(text: str, mall_id: str) -> None:
    assert mentioned_seed_mall_ids(text, load_master_data()) == [mall_id]


# ---- MasterDataSource -----------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 27, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class _FlakySource:
    name = "flaky"

    def __init__(self, data: MasterData) -> None:
        self.data = data
        self.fail = False
        self.calls = 0

    def fetch(self) -> MasterData:
        self.calls += 1
        if self.fail:
            raise MasterDataUnavailable("down")
        return self.data


def test_cache_refreshes_daily_and_keeps_last_good_copy() -> None:
    seed = SeedMasterDataSource().fetch()
    source = _FlakySource(seed)
    clock = _Clock()
    cache = CachedMasterData(source, clock=clock)

    assert cache.get() is seed
    clock.now += timedelta(hours=23)
    cache.get()
    assert source.calls == 1  # still fresh

    clock.now += timedelta(hours=2)
    source.fail = True
    assert cache.get() is seed  # refresh failed: last good copy
    assert source.calls == 2


def test_cenomi_stub_falls_back_to_seed() -> None:
    cache = CachedMasterData(CenomiMasterDataSource(), fallback=SeedMasterDataSource())
    assert "riyadh-mall-a" in cache.get().mall_ids()


def test_cenomi_stub_without_fallback_raises() -> None:
    with pytest.raises(MasterDataUnavailable):
        CachedMasterData(CenomiMasterDataSource()).get()
