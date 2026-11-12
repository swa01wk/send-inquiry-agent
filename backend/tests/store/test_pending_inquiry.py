"""Flow v2 pending inquiry in the repository (spec flow-v2-alignment §3.3, FV12; day F3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.domain.models import FieldKey
from app.store.memory import InMemoryInquiryRepository
from app.store.models import Inquiry, InquiryStatus

pytestmark = pytest.mark.unit

EMAIL = "sara@brand.example"
TTL = timedelta(minutes=120)


@pytest.fixture
def repo() -> InMemoryInquiryRepository:
    return InMemoryInquiryRepository(draft_retention_days=30)


def _verify(inquiry: Inquiry, *, flow: str = "v2", at: datetime | None = None) -> None:
    draft = inquiry.draft
    draft.intake_flow = flow  # type: ignore[assignment]
    draft.fields[FieldKey.EMAIL].value = EMAIL
    draft.email_verified = True
    draft.verified_at = at or datetime.now(tz=UTC)


async def test_verified_v2_inquiry_becomes_pending(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry)
    saved = await repo.save(inquiry)
    assert saved.status == InquiryStatus.PENDING


async def test_v1_inquiry_stays_a_draft_when_verified(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry, flow="v1")
    saved = await repo.save(inquiry)
    assert saved.status == InquiryStatus.DRAFT


async def test_unverified_v2_inquiry_stays_a_draft(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    inquiry.draft.intake_flow = "v2"
    saved = await repo.save(inquiry)
    assert saved.status == InquiryStatus.DRAFT


async def test_registered_cr_is_never_pending(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry)
    inquiry.draft.cr_status = "existing"
    saved = await repo.save(inquiry)
    assert saved.status == InquiryStatus.DRAFT


async def test_pending_inquiry_is_submitted_with_a_reference(
    repo: InMemoryInquiryRepository,
) -> None:
    inquiry = await repo.create()
    _verify(inquiry)
    pending = await repo.save(inquiry)
    pending.draft.reference = "INQ-2026-OFF-0001"
    submitted = await repo.save(pending)
    assert submitted.status == InquiryStatus.SUBMITTED


async def test_pending_by_email_finds_the_newest(repo: InMemoryInquiryRepository) -> None:
    older = await repo.create()
    _verify(older)
    await repo.save(older)
    newer = await repo.create()
    _verify(newer)
    newer_saved = await repo.save(newer)
    found = await repo.pending_by_email(EMAIL)
    assert found is not None
    assert found.id == newer_saved.id
    assert await repo.pending_by_email("nobody@brand.example") is None


async def test_pending_by_email_ignores_drafts(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry, flow="v1")
    await repo.save(inquiry)
    assert await repo.pending_by_email(EMAIL) is None


async def test_expire_pending_after_the_ttl(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry)
    saved = await repo.save(inquiry)
    now = saved.last_seen_at + TTL - timedelta(minutes=1)
    assert await repo.expire_pending(now, TTL) == []
    later = saved.last_seen_at + TTL + timedelta(minutes=1)
    assert await repo.expire_pending(later, TTL) == [saved.id]
    assert (await repo.get(saved.id)).status == InquiryStatus.ABANDONED
    assert await repo.pending_by_email(EMAIL) is None


async def test_recent_activity_keeps_a_pending_inquiry(repo: InMemoryInquiryRepository) -> None:
    inquiry = await repo.create()
    _verify(inquiry, at=datetime.now(tz=UTC) - TTL * 2)
    saved = await repo.save(inquiry)
    assert await repo.expire_pending(datetime.now(tz=UTC), TTL) == []
    assert (await repo.get(saved.id)).status == InquiryStatus.PENDING
