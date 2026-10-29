"""Attention items in memory, and in `<DATA_DIR>/proactive/items.json` when set."""

from __future__ import annotations

import threading

from app.persistence import JsonFile, data_path
from app.proactive.models import AttentionItem


class AttentionStore:
    def __init__(self, data_dir: str | None = None) -> None:
        self._file = JsonFile(data_path(data_dir, "proactive", "items.json"))
        raw = self._file.load([])
        self._items: dict[str, AttentionItem] = {
            item.id: item for item in (AttentionItem.model_validate(r) for r in raw)
        }
        self._lock = threading.Lock()

    def _flush(self) -> None:
        self._file.save([i.model_dump(mode="json") for i in self._items.values()])

    def get(self, item_id: str) -> AttentionItem | None:
        with self._lock:
            item = self._items.get(item_id)
            return item.model_copy(deep=True) if item else None

    def has_key(self, key: str) -> bool:
        with self._lock:
            return any(i.key == key for i in self._items.values())

    def save(self, item: AttentionItem) -> None:
        with self._lock:
            self._items[item.id] = item.model_copy(deep=True)
            self._flush()

    def all(self) -> list[AttentionItem]:
        with self._lock:
            return [i.model_copy(deep=True) for i in self._items.values()]
