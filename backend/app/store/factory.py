"""Repository factory from application settings."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.sessions import SessionStore
from app.store.handle_store import PostgresHandleStore
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


def make_session_store(settings: Settings) -> SessionStore:
    if settings.state_backend == "postgres":
        if not settings.database_url:
            msg = "DATABASE_URL is required when STATE_BACKEND=postgres"
            raise RuntimeError(msg)
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        repo = PostgresInquiryRepository(
            factory,
            draft_retention_days=settings.draft_retention_days,
        )
        handles = PostgresHandleStore(factory)
        return SessionStore(
            repo,
            ttl_minutes=settings.session_ttl_minutes,
            handle_store=handles,
            postgres_handles=True,
        )
    return SessionStore(
        InMemoryInquiryRepository(draft_retention_days=settings.draft_retention_days),
        ttl_minutes=settings.session_ttl_minutes,
        data_dir=settings.data_dir,
    )
