"""SQLAlchemy table definitions for durable inquiries."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InquiryRow(Base):
    __tablename__ = "inquiries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    draft: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cards_shown: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confirm_card_keys: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    card_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submit_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turn_lease_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    turn_lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="self_service")
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    staff_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (Index("ix_inquiries_status_expires_at", "status", "expires_at"),)


class SessionHandleRow(Base):
    __tablename__ = "session_handles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    inquiry_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inquiries.id"), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handle_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class InquiryEventRow(Base):
    __tablename__ = "inquiry_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inquiry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inquiries.id"), nullable=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("inquiry_id", "seq", name="uq_inquiry_events_inquiry_seq"),
        Index("ix_inquiry_events_inquiry_seq", "inquiry_id", "seq"),
    )
