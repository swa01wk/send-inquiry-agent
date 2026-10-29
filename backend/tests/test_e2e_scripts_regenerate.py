from __future__ import annotations

from pathlib import Path

import pytest

from tests.scenarios.catalogue import (
    HAND_WRITTEN_E2E_SCRIPTS,
    e2e_script_json_text,
    list_by_layer,
)

pytestmark = pytest.mark.agent

_SCRIPTS_DIR = Path(__file__).resolve().parent / "e2e_scripts"


@pytest.mark.parametrize("name", list_by_layer("e2e_script"))
def test_generated_e2e_script_matches_catalogue(name: str) -> None:
    assert name not in HAND_WRITTEN_E2E_SCRIPTS
    expected = e2e_script_json_text(name)
    on_disk = (_SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8")
    assert on_disk == expected
