"""inquiries, session_handles, inquiry_events

Revision ID: 0001_inquiries
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_inquiries"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("draft", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cards_shown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confirm_card_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("card_counter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submit_key", sa.String(length=128), nullable=True),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turn_lease_id", sa.String(length=64), nullable=True),
        sa.Column("turn_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="self_service"),
        sa.Column("case_id", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("staff_id", sa.String(length=64), nullable=True),
        sa.Column("session_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submit_key"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_inquiries_status_expires_at", "inquiries", ["status", "expires_at"])

    op.create_table(
        "session_handles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handle_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "inquiry_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inquiry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["inquiry_id"], ["inquiries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inquiry_id", "seq", name="uq_inquiry_events_inquiry_seq"),
    )
    op.create_index("ix_inquiry_events_inquiry_seq", "inquiry_events", ["inquiry_id", "seq"])


def downgrade() -> None:
    op.drop_index("ix_inquiry_events_inquiry_seq", table_name="inquiry_events")
    op.drop_table("inquiry_events")
    op.drop_table("session_handles")
    op.drop_index("ix_inquiries_status_expires_at", table_name="inquiries")
    op.drop_table("inquiries")
