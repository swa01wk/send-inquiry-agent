"""Repository factory from application settings."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.store.memory import InMemoryInquiryRepository
from app.store.postgres import PostgresInquiryRepository
from app.store.repository import InquiryRepository


def make_inquiry_repository(settings: Settings) -> InquiryRepository:
    if settings.state_backend == "postgres":
        if not settings.database_url:
            msg = "DATABASE_URL is required when STATE_BACKEND=postgres"
            raise RuntimeError(msg)
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        return PostgresInquiryRepository(
            factory,
            draft_retention_days=settings.draft_retention_days,
        )
    return InMemoryInquiryRepository(draft_retention_days=settings.draft_retention_days)
