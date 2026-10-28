"""Yardi, simulated (L4 §3.2, §3.7; assumption A7).

Company search by the first word of the company name, active companies only
(requirements §7.1.1 c); brands from that company's previous leases and proposals;
`send_lead` returns a lead reference and is idempotent on its key.
"""

from __future__ import annotations

import json
import random
import threading
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from app.persistence import JsonFile, data_path

YARDI_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_world" / "yardi.json"


class YardiBrand(BaseModel):
    id: str
    name: str
    source: str  # "lease" | "proposal"


class YardiCompany(BaseModel):
    id: str
    name: str
    active: bool
    brands: list[YardiBrand]


class YardiService(Protocol):
    def search_companies(self, name: str) -> list[YardiCompany]: ...

    def brands_for_company(self, company_id: str) -> list[YardiBrand]: ...

    def send_lead(self, payload: dict[str, Any], *, idempotency_key: str) -> str: ...


class MockYardiService:
    def __init__(self, data_dir: str | None = None) -> None:
        raw = json.loads(YARDI_PATH.read_text(encoding="utf-8"))
        self._companies = [YardiCompany.model_validate(c) for c in raw["companies"]]
        self._file = JsonFile(data_path(data_dir, "mock_world", "yardi_leads.json"))
        self._leads: dict[str, dict[str, Any]] = dict(self._file.load({}))
        self._lock = threading.Lock()

    def search_companies(self, name: str) -> list[YardiCompany]:
        words = name.strip().split()
        if not words:
            return []
        first = words[0].lower()
        return [
            c
            for c in self._companies
            if c.active and first in [w.lower().strip(".,&") for w in c.name.split()]
        ]

    def company(self, company_id: str) -> YardiCompany | None:
        return next((c for c in self._companies if c.id == company_id), None)

    def brands_for_company(self, company_id: str) -> list[YardiBrand]:
        company = self.company(company_id)
        return list(company.brands) if company else []

    def send_lead(self, payload: dict[str, Any], *, idempotency_key: str) -> str:
        with self._lock:
            existing = self._leads.get(idempotency_key)
            if existing is not None:
                return str(existing["lead_ref"])
            lead_ref = f"YL-{random.randint(0, 999_999):06d}"
            self._leads[idempotency_key] = {"lead_ref": lead_ref, "payload": payload}
            self._file.save(self._leads)
            return lead_ref

    @property
    def leads(self) -> dict[str, dict[str, Any]]:
        return self._leads
