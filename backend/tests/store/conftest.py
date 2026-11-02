"""Postgres repository fixtures."""

from __future__ import annotations

import os

import pytest
from app.store.postgres import PostgresInquiryRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "postgres: requires TEST_DATABASE_URL")


@pytest.fixture
async def pg_repo() -> PostgresInquiryRepository:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    repo = PostgresInquiryRepository(factory, draft_retention_days=30)
    yield repo
    await engine.dispose()
