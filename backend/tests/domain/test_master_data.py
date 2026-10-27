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
