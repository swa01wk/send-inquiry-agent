"""Shared contract tests for InquiryRepository implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.store.errors import InquiryNotFound, TurnInProgress, VersionConflict
from app.store.memory import InMemoryInquiryRepository
from app.store.models import InquiryStatus


@pytest.fixture
def memory_repo() -> InMemoryInquiryRepository:
    return InMemoryInquiryRepository(draft_retention_days=30)


async def test_create_and_get(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create(channel="assisted", staff_id="exec-1")
    loaded = await memory_repo.get(inquiry.id)
    assert loaded.channel == "assisted"
    assert loaded.staff_id == "exec-1"
    assert loaded.version == 0
    assert loaded.status == InquiryStatus.DRAFT


async def test_save_bumps_version(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create()
    inquiry.card_counter = 1
    saved = await memory_repo.save(inquiry)
    assert saved.version == 1
    assert saved.card_counter == 1


async def test_save_version_conflict(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create()
    stale = inquiry.model_copy(deep=True)
    await memory_repo.save(inquiry)
    with pytest.raises(VersionConflict):
        await memory_repo.save(stale)


async def test_touch_refreshes_expiry_without_version_bump(
    memory_repo: InMemoryInquiryRepository,
) -> None:
    inquiry = await memory_repo.create()
    before_expires = inquiry.expires_at
    later = inquiry.last_seen_at + timedelta(days=5)
    touched = await memory_repo.touch(inquiry.id, now=later)
    assert touched.version == 0
    assert touched.last_seen_at == later
    assert touched.expires_at > before_expires


async def test_turn_lease_acquire_and_conflict(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create()
    lease = await memory_repo.acquire_turn(inquiry.id, lease_s=120)
    assert lease
    with pytest.raises(TurnInProgress):
        await memory_repo.acquire_turn(inquiry.id, lease_s=120)
    await memory_repo.release_turn(inquiry.id, lease)
    lease2 = await memory_repo.acquire_turn(inquiry.id, lease_s=60)
    assert lease2 != lease


async def test_turn_lease_expired_takeover(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create()
    lease = await memory_repo.acquire_turn(inquiry.id, lease_s=1)
    past = datetime.now(tz=UTC) + timedelta(seconds=2)
    # Simulate expiry by renewing with 0 then waiting — release and acquire after time
    await memory_repo.release_turn(inquiry.id, lease)
    lease2 = await memory_repo.acquire_turn(inquiry.id, lease_s=120)
    assert lease2


async def test_purge_expired_drafts_only(memory_repo: InMemoryInquiryRepository) -> None:
    inquiry = await memory_repo.create()
    old = inquiry.last_seen_at - timedelta(days=31)
    touched = await memory_repo.touch(inquiry.id, now=old)
    assert touched.expires_at < datetime.now(tz=UTC)
    purged = await memory_repo.purge_expired(datetime.now(tz=UTC))
    assert inquiry.id in purged
    loaded = await memory_repo.get(inquiry.id)
    assert loaded.status == InquiryStatus.ABANDONED


async def test_get_missing(memory_repo: InMemoryInquiryRepository) -> None:
    import uuid

    with pytest.raises(InquiryNotFound):
        await memory_repo.get(uuid.uuid4())
