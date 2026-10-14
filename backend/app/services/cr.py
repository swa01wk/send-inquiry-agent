"""Commercial registration verification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CrResult:
    exists: bool
    company_name: str | None = None
    company_address: str | None = None


class CrService(Protocol):
    def verify(self, cr_number: str) -> CrResult: ...


class MockCrService:
    _EXISTING = "1010000000"
    _NEW_WITH_DETAILS = "1010123456"
    _COMPANY = "Bean Street Trading Co."
    _ADDRESS = "King Fahd Road, Al Olaya, Riyadh"

    def verify(self, cr_number: str) -> CrResult:
        if cr_number == self._EXISTING:
            return CrResult(exists=True)
        if cr_number == self._NEW_WITH_DETAILS:
            return CrResult(
                exists=False,
                company_name=self._COMPANY,
                company_address=self._ADDRESS,
            )
        return CrResult(exists=False)
