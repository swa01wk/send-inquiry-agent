#!/usr/bin/env python3
"""Generate backend/tests/e2e_scripts/*.json for Playwright @scripted runs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.scenarios.catalogue import (  # noqa: E402
    e2e_script_json_text,
    list_by_layer,
)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--flow-v2",
        action="store_true",
        help="Regenerate flow-v2-s01…s17 intake scripts from docs/flow-v2/scenarios.json",
    )
    args = parser.parse_args()

    out_dir = ROOT / "tests" / "e2e_scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.flow_v2:
        compile_path = Path(__file__).resolve().parent / "flow_v2_e2e_compile.py"
        spec = importlib.util.spec_from_file_location("flow_v2_e2e_compile", compile_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        n = mod.write_intake_scripts(out_dir)
        print(f"Wrote {n} flow-v2 intake scripts to {out_dir}")
        return

    names = list_by_layer("e2e_script")
    for name in names:
        path = out_dir / f"{name}.json"
        path.write_text(e2e_script_json_text(name), encoding="utf-8")
    print(f"Wrote {len(names)} scripts to {out_dir}")


if __name__ == "__main__":
    main()
