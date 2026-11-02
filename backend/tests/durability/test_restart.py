"""Inquiry survives process restart (step 13)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from app.sessions import SessionStore
from app.store.memory import InMemoryInquiryRepository
from app.store.postgres import PostgresInquiryRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.postgres


def _migrate(url: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        env=env,
        check=True,
    )


@pytest.fixture
async def postgres_store() -> SessionStore:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    _migrate(url)
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    from app.store.handle_store import PostgresHandleStore

    repo = PostgresInquiryRepository(factory, draft_retention_days=30)
    handles = PostgresHandleStore(factory)
    store = SessionStore(
        repo,
        ttl_minutes=120,
        handle_store=handles,
        postgres_handles=True,
    )
    yield store
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_survives_new_store_instance(postgres_store: SessionStore) -> None:
    session = await postgres_store.create()
    session.add_message("u1", "user", "hello")
    session.card_counter = 2
    await postgres_store.save(session)

    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    from app.store.handle_store import PostgresHandleStore

    repo = PostgresInquiryRepository(factory, draft_retention_days=30)
    handles = PostgresHandleStore(factory)
    restarted = SessionStore(
        repo,
        ttl_minutes=120,
        handle_store=handles,
        postgres_handles=True,
    )
    loaded = await restarted.get(session.id)
    assert loaded.transcript == session.transcript
    assert loaded.card_counter == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_json_restart_unchanged(tmp_path) -> None:
    store = SessionStore(InMemoryInquiryRepository(), ttl_minutes=120, data_dir=str(tmp_path))
    session = await store.create()
    session.turn_index = 3
    await store.save(session)
    again = SessionStore(InMemoryInquiryRepository(), ttl_minutes=120, data_dir=str(tmp_path))
    loaded = await again.get(session.id)
    assert loaded.turn_index == 3
