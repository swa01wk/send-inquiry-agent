"""Commercial registration verification (simulated CR registry, L3 §3.1).

Scenario data: `app/data/mock_world/cr_registry.json`. Unknown numbers are "new, no
details". Fault numbers raise the same errors a real outage would, so the gateway maps
them to `timeout` or `unavailable`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.services.errors import ServiceTimeout, ServiceUnavailable

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_world" / "cr_registry.json"


@dataclass(frozen=True)
class CrResult:
    exists: bool
    company_name: str | None = None
    company_address: str | None = None


class CrService(Protocol):
    def verify(self, cr_number: str) -> CrResult: ...


class MockCrService:
    def __init__(self, registry_path: Path = REGISTRY_PATH) -> None:
        raw: dict[str, Any] = json.loads(registry_path.read_text(encoding="utf-8"))
        self._records: dict[str, dict[str, Any]] = {r["cr_number"]: r for r in raw["records"]}

    def verify(self, cr_number: str) -> CrResult:
        record = self._records.get(cr_number)
        if record is None:
            return CrResult(exists=False)
        outcome = record["outcome"]
        if outcome == "fault":
            if record.get("fault") == "timeout":
                raise ServiceTimeout("CR registry did not answer")
            raise ServiceUnavailable("CR registry is unavailable")
        if outcome == "existing":
            return CrResult(exists=True)
        return CrResult(
            exists=False,
            company_name=record.get("company_name"),
            company_address=record.get("company_address"),
        )
