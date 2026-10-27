"""Small JSON files for restart-safe state (DELIVERY-PLAN §A5: a JSON snapshot store).

With no directory configured (tests, Playwright) nothing is written and state lives in
memory only. Writes are atomic: a temp file, then a rename.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonFile:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def load(self, default: Any) -> Any:
        if self.path is None or not self.path.exists():
            return default
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Any) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=1, default=str)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def data_path(data_dir: str | None, *parts: str) -> Path | None:
    """`<DATA_DIR>/<parts…>`, or None when persistence is off."""
    if not data_dir:
        return None
    return Path(data_dir).joinpath(*parts)
