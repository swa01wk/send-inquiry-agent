"""LangGraph checkpointers with domain types on the msgpack allowlist."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

_CHECKPOINT_MSGPACK_ALLOWLIST = [
    ("app.domain.models", "Source"),
    ("app.domain.models", "InquiryDraft"),
    ("app.domain.models", "DocType"),
]


def checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MSGPACK_ALLOWLIST)


def memory_checkpointer() -> MemorySaver:
    return MemorySaver(serde=checkpoint_serde())


def psycopg_conn_string(database_url: str) -> str:
    """LangGraph's Postgres saver expects a ``postgresql://`` URL (psycopg 3)."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url


def postgres_checkpointer(
    database_url: str,
) -> AbstractAsyncContextManager[AsyncPostgresSaver]:
    """Async context manager yielding a configured ``AsyncPostgresSaver``."""
    return AsyncPostgresSaver.from_conn_string(
        psycopg_conn_string(database_url),
        serde=checkpoint_serde(),
    )
