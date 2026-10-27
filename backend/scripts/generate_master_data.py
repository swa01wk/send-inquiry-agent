#!/usr/bin/env python3
"""Generate the seed master data (docs/specs/l3-reliable-intake.md §3.8).

Writes app/data/master_data.json: regions with cities, about 20 synthetic malls with
English and Arabic names, aliases, city and region; product lines with codes; sales
categories, lease and rent periods with Arabic labels.

The output is fully determined by the tables below (no randomness), so two runs are
byte-identical. Names are clearly synthetic until Cenomi supplies its list (assumption 6).
Existing ids never change, so goldens and e2e scripts don't move; new malls go into new
cities so the existing cities' mall pickers are unchanged.

Usage:
    cd backend && uv run python scripts/generate_master_data.py          # write
    cd backend && uv run python scripts/generate_master_data.py --check  # fail if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "master_data.json"

REGIONS: list[tuple[str, str, str]] = [
    ("central", "Central", "المنطقة الوسطى"),
    ("western", "Western", "المنطقة الغربية"),
    ("eastern", "Eastern", "المنطقة الشرقية"),
]

# (id, English, Arabic, region). The first three are today's cities, in today's order.
CITIES: list[tuple[str, str, str, str]] = [
    ("riyadh", "Riyadh", "الرياض", "central"),
    ("jeddah", "Jeddah", "جدة", "western"),
    ("dammam", "Dammam", "الدمام", "eastern"),
    ("buraidah", "Buraidah", "بريدة", "central"),
    ("makkah", "Makkah", "مكة المكرمة", "western"),
    ("madinah", "Madinah", "المدينة المنورة", "western"),
    ("khobar", "Al Khobar", "الخبر", "eastern"),
    ("jubail", "Jubail", "الجبيل", "eastern"),
]

# Arabic form of the city used in synthetic mall names ("<city> مول أ").
CITY_IN_MALL_NAME_AR: dict[str, str] = {
    "riyadh": "الرياض",
    "jeddah": "جدة",
    "dammam": "الدمام",
    "buraidah": "بريدة",
    "makkah": "مكة",
    "madinah": "المدينة",
    "khobar": "الخبر",
    "jubail": "الجبيل",
}

LETTERS_AR: dict[str, str] = {"A": "أ", "B": "ب", "C": "ج", "D": "د"}

# Lettered malls per city: (city id, English city word in the name, letters).
# Today's lettered malls first (ids unchanged), then the new cities.
LETTERED_MALLS: list[tuple[str, str, str]] = [
    ("riyadh", "Riyadh", "ABCD"),
    ("jeddah", "Jeddah", "AB"),
    ("dammam", "Dammam", "A"),
    ("buraidah", "Buraidah", "AB"),
    ("makkah", "Makkah", "ABC"),
    ("madinah", "Madinah", "AB"),
    ("khobar", "Khobar", "ABC"),
    ("jubail", "Jubail", "A"),
]

# Named malls (ids unchanged): id, English, Arabic, city, English aliases, Arabic aliases.
NAMED_MALLS: list[tuple[str, str, str, str, list[str], list[str]]] = [
    ("mall-of-arabia", "Mall of Arabia", "مول العرب", "jeddah", ["Arabia Mall"], ["العرب مول"]),
    ("mall-of-dhahran", "Mall of Dhahran", "مول الظهران", "dammam", [], ["الظهران مول"]),
]

# Where each named mall sits in the output, to keep today's order.
NAMED_AFTER: dict[str, str] = {
    "mall-of-arabia": "jeddah-mall-b",
    "mall-of-dhahran": "dammam-mall-a",
}

UNIT_TYPES: list[tuple[str, str, str, str]] = [
    ("store", "Store", "متجر", "STR"),
    ("media", "Media", "مساحة إعلانية", "MED"),
    ("specialty", "Specialty", "وحدة متخصصة", "SPC"),
]

SALES_CATEGORIES: list[tuple[str, str, str]] = [
    ("fnb_cafe", "Food & Beverage · Café", "أغذية ومشروبات · مقهى"),
    ("fnb_restaurant", "Food & Beverage · Restaurant", "أغذية ومشروبات · مطعم"),
    ("fashion", "Fashion & Apparel", "أزياء وملابس"),
    ("beauty", "Health & Beauty", "صحة وجمال"),
    ("electronics", "Electronics", "إلكترونيات"),
    ("entertainment", "Entertainment", "ترفيه"),
    ("services", "Services", "خدمات"),
]

LEASE_PERIODS: list[tuple[str, str, str]] = [
    ("1y", "1 year", "سنة واحدة"),
    ("2y", "2 years", "سنتان"),
    ("3y", "3 years", "3 سنوات"),
    ("5y", "5 years", "5 سنوات"),
]

RENT_PERIODS: list[tuple[str, str, str]] = [
    ("monthly", "Monthly", "شهري"),
    ("yearly", "Yearly", "سنوي"),
]


def _without_hamza(text: str) -> str:
    """A common spelling variant: users often type ا for أ."""
    return text.replace("أ", "ا")


def _lettered_mall(city_id: str, city_word: str, letter: str, region: str) -> dict[str, Any]:
    name_ar = f"{CITY_IN_MALL_NAME_AR[city_id]} مول {LETTERS_AR[letter]}"
    aliases_ar = [f"مول {CITY_IN_MALL_NAME_AR[city_id]} {LETTERS_AR[letter]}"]
    if _without_hamza(name_ar) != name_ar:
        aliases_ar.append(_without_hamza(name_ar))
    return {
        "id": f"{city_id}-mall-{letter.lower()}",
        "name": f"{city_word} Mall {letter}",
        "name_ar": name_ar,
        "city": city_id,
        "region": region,
        "aliases": aliases_ar,
    }


def build() -> dict[str, Any]:
    region_of = {city_id: region for city_id, _en, _ar, region in CITIES}

    malls: list[dict[str, Any]] = []
    for city_id, city_word, letters in LETTERED_MALLS:
        for letter in letters:
            malls.append(_lettered_mall(city_id, city_word, letter, region_of[city_id]))
    for mall_id, name, name_ar, city_id, aliases_en, aliases_ar in NAMED_MALLS:
        entry = {
            "id": mall_id,
            "name": name,
            "name_ar": name_ar,
            "city": city_id,
            "region": region_of[city_id],
            "aliases": [*aliases_en, *aliases_ar],
        }
        anchor = next(i for i, m in enumerate(malls) if m["id"] == NAMED_AFTER[mall_id])
        malls.insert(anchor + 1, entry)

    return {
        "regions": [{"id": i, "label": en, "label_ar": ar} for i, en, ar in REGIONS],
        "unit_types": [
            {"id": i, "label": en, "label_ar": ar, "code": code} for i, en, ar, code in UNIT_TYPES
        ],
        "sales_categories": [
            {"id": i, "label": en, "label_ar": ar} for i, en, ar in SALES_CATEGORIES
        ],
        "cities": [
            {"id": i, "label": en, "label_ar": ar, "region": region} for i, en, ar, region in CITIES
        ],
        "malls": malls,
        "lease_periods": [{"id": i, "label": en, "label_ar": ar} for i, en, ar in LEASE_PERIODS],
        "rent_periods": [{"id": i, "label": en, "label_ar": ar} for i, en, ar in RENT_PERIODS],
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if app/data/master_data.json differs from the generated output",
    )
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"{OUTPUT} is out of date; run scripts/generate_master_data.py", file=sys.stderr)
            return 1
        print(f"{OUTPUT} is up to date")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(build()['malls'])} malls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
