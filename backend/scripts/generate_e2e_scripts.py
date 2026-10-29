#!/usr/bin/env python3
"""Generate backend/tests/e2e_scripts/*.json for Playwright @scripted runs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.scenarios.catalogue import (  # noqa: E402
    e2e_script_json_text,
    list_by_layer,
)


def main() -> None:
    out_dir = ROOT / "tests" / "e2e_scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list_by_layer("e2e_script")
    for name in names:
        path = out_dir / f"{name}.json"
        path.write_text(e2e_script_json_text(name), encoding="utf-8")
    print(f"Wrote {len(names)} scripts to {out_dir}")


if __name__ == "__main__":
    main()
