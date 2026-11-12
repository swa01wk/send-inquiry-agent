"""Draft retention purge (M0 §5.4)."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.store.repository import InquiryRepository

logger = logging.getLogger(__name__)


async def expire_pending_inquiries(repo: InquiryRepository, *, now: datetime | None = None) -> int:
    """Flow v2 pending inquiries past the TTL since last activity → abandoned (FV12)."""
    from app.policy.config import get_policy

    ttl = timedelta(minutes=get_policy().flow_v2_intake.pending_inquiry_ttl_minutes)
    expired = await repo.expire_pending(now or datetime.now(tz=UTC), ttl)
    if expired:
        logger.info("expired %d pending inquiry(ies)", len(expired))
    return len(expired)


async def purge_expired_inquiries(
    repo: InquiryRepository,
    *,
    settings: Settings,
    checkpointer: object | None = None,
    now: datetime | None = None,
) -> int:
    ts = now or datetime.now(tz=UTC)
    await expire_pending_inquiries(repo, now=ts)
    purged = await repo.purge_expired(ts)
    for inquiry_id in purged:
        thread_id = str(inquiry_id)
        if checkpointer is not None and hasattr(checkpointer, "adelete_thread"):
            try:
                await checkpointer.adelete_thread(thread_id)
            except Exception:
                logger.exception("failed to delete checkpoint thread %s", thread_id)
        upload_root = Path(settings.upload_dir) / thread_id
        if upload_root.exists():
            shutil.rmtree(upload_root, ignore_errors=True)
    if purged:
        logger.info("purged %d expired draft(s)", len(purged))
    return len(purged)
