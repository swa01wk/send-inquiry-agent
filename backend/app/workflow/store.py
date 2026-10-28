"""Cases, kept in memory and, with `DATA_DIR`, in `<DATA_DIR>/cases/<reference>.json`.

Day 4 depth (DELIVERY-PLAN §A5): JSON snapshots, like sessions. Postgres and the
`case_effects` table arrive in Sprint 2.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

from app.persistence import JsonFile, data_path
from app.workflow.models import Case

logger = logging.getLogger(__name__)
_SAFE = re.compile(r"[^A-Za-z0-9_-]")


class CaseStore:
    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = data_dir
        self._cases: dict[str, Case] = {}
        self._lock = threading.Lock()
        directory = data_path(data_dir, "cases")
        if directory is not None and directory.exists():
            for path in sorted(Path(directory).glob("*.json")):
                try:
                    case = Case.model_validate(JsonFile(path).load({}))
                except Exception:  # a damaged snapshot shouldn't stop the app
                    logger.warning("skipping unreadable case snapshot %s", path.name)
                    continue
                self._cases[case.id] = case

    def _file(self, case_id: str) -> JsonFile:
        return JsonFile(data_path(self._data_dir, "cases", f"{_SAFE.sub('_', case_id)}.json"))

    def get(self, case_id: str) -> Case | None:
        with self._lock:
            case = self._cases.get(case_id)
            return case.model_copy(deep=True) if case else None

    def save(self, case: Case) -> None:
        with self._lock:
            self._cases[case.id] = case.model_copy(deep=True)
            self._file(case.id).save(case.model_dump(mode="json"))

    def all(self) -> list[Case]:
        with self._lock:
            return [c.model_copy(deep=True) for c in self._cases.values()]
