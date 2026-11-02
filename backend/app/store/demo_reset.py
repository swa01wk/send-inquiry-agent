"""Postgres cleanup for dev demo reset."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def truncate_postgres_demo_state(database_url: str) -> None:
    """Clear inquiry rows and LangGraph checkpoints (dev reset only)."""
    engine = create_async_engine(database_url, pool_pre_ping=True)
    truncate_sql = text(
        "TRUNCATE TABLE checkpoint_writes, checkpoint_blobs, checkpoints, "
        "inquiry_events, session_handles, inquiries RESTART IDENTITY CASCADE"
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(truncate_sql)
    finally:
        await engine.dispose()
