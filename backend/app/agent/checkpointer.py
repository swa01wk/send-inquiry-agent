"""In-memory LangGraph checkpointer with domain types on the msgpack allowlist."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

_CHECKPOINT_MSGPACK_ALLOWLIST = [
    ("app.domain.models", "Source"),
    ("app.domain.models", "InquiryDraft"),
    ("app.domain.models", "DocType"),
]


def memory_checkpointer() -> MemorySaver:
    serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MSGPACK_ALLOWLIST)
    return MemorySaver(serde=serde)
