"""Inquiry submission (simulated Tenant Admin Platform inbox, L3 §3.1).

`submit` takes an idempotency key: the same key always returns the same reference, so a
repeated Submit can't create a second inquiry. Submissions survive a restart when
`DATA_DIR` is set (a real platform wouldn't forget them when our backend restarts).
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Any, Protocol

from app import clock
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft
from app.persistence import JsonFile, data_path

logger = logging.getLogger(__name__)

_UNIT_CODES = ("STR", "MED", "SPC")
_DEFAULT_CODE = "STR"


class SubmitService(Protocol):
    def submit(
        self, draft: InquiryDraft, master: MasterData, *, idempotency_key: str | None = None
    ) -> str: ...

    def lookup(self, idempotency_key: str) -> str | None: ...


class MockSubmitService:
    def __init__(self, data_dir: str | None = None) -> None:
        self._file = JsonFile(data_path(data_dir, "mock_world", "submissions.json"))
        state = self._file.load({})
        self._submissions: dict[str, dict[str, Any]] = dict(state.get("submissions", {}))
        self._keys: dict[str, str] = dict(state.get("keys", {}))
        self._lock = threading.Lock()

    @property
    def submissions(self) -> dict[str, dict[str, Any]]:
        return self._submissions

    def lookup(self, idempotency_key: str) -> str | None:
        return self._keys.get(idempotency_key)

    def submit(
        self, draft: InquiryDraft, master: MasterData, *, idempotency_key: str | None = None
    ) -> str:
        with self._lock:
            if idempotency_key and idempotency_key in self._keys:
                return self._keys[idempotency_key]
            unit_type_id = draft.fields[FieldKey.UNIT_TYPE].value
            code = master.unit_code(str(unit_type_id)) if unit_type_id else None
            if code not in _UNIT_CODES:
                code = _DEFAULT_CODE
            reference = f"GEO-{code}-{random.randint(0, 999_999):06d}"
            while reference in self._submissions:
                reference = f"GEO-{code}-{random.randint(0, 999_999):06d}"
            payload = draft.model_dump(mode="json")
            payload["submitted_at"] = clock.now().isoformat()
            self._submissions[reference] = payload
            if idempotency_key:
                self._keys[idempotency_key] = reference
            self._file.save({"submissions": self._submissions, "keys": self._keys})
        logger.info("Inquiry submitted reference=%s", reference)
        return reference
