#!/usr/bin/env -S uv run python
"""Regenerate backend/tests/parity/golden/*.jsonl (deliberate commit required)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from tests.parity.recorder import record_all


def main() -> None:
    settings = Settings(
        upload_dir=str(Path(__file__).resolve().parents[1] / ".golden-uploads"),
        max_upload_mb=5,
        session_ttl_minutes=120,
        dev_tools=True,
        token_secret="golden-record-secret",
        email_link_demo=True,
        agent_mode="scripted",
    )
    asyncio.run(record_all(settings))


if __name__ == "__main__":
    main()
