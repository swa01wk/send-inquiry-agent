"""Ensure Postgres schema matches Alembic head before serving traffic."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
_NOT_MIGRATED_MSG = "database not migrated: run alembic upgrade head"


def assert_postgres_schema_at_head(database_url: str) -> None:
    """Raise if ``alembic_version`` is missing or not at script head."""
    cfg = Config(str(_ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    if head is None:
        return

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()
    finally:
        engine.dispose()

    if current != head:
        logger.error("%s (current=%s, head=%s)", _NOT_MIGRATED_MSG, current, head)
        raise RuntimeError(_NOT_MIGRATED_MSG)
