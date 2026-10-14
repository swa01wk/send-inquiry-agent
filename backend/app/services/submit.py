"""Inquiry submission."""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime
from typing import Any, Protocol

from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft

logger = logging.getLogger(__name__)

_UNIT_CODES = ("STR", "MED", "SPC", "OFF")
_DEFAULT_CODE = "STR"


class SubmitService(Protocol):
    def submit(self, draft: InquiryDraft, master: MasterData) -> str: ...


class MockSubmitService:
    def __init__(self) -> None:
        self._submissions: dict[str, dict[str, Any]] = {}

    @property
    def submissions(self) -> dict[str, dict[str, Any]]:
        return self._submissions

    def submit(self, draft: InquiryDraft, master: MasterData) -> str:
        unit_type_id = draft.fields[FieldKey.UNIT_TYPE].value
        code = master.unit_code(str(unit_type_id)) if unit_type_id else None
        if code not in _UNIT_CODES:
            code = _DEFAULT_CODE

        reference = f"GEO-{code}-{random.randint(0, 999_999):06d}"
        payload = draft.model_dump(mode="json")
        payload["submitted_at"] = datetime.now(tz=UTC).isoformat()
        self._submissions[reference] = payload
        logger.info("Inquiry submitted reference=%s", reference)
        return reference
