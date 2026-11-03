"""The memory repository enforces the unique reference the Postgres column does."""

from __future__ import annotations

import pytest
from app.store.errors import DuplicateReference
from app.store.memory import InMemoryInquiryRepository


async def test_memory_repo_rejects_a_second_owner_of_a_reference() -> None:
    repo = InMemoryInquiryRepository(draft_retention_days=30)
    first = await repo.create()
    first.draft.reference = "GEO-STR-000001"
    await repo.save(first)

    second = await repo.create()
    second.draft.reference = "GEO-STR-000001"
    with pytest.raises(DuplicateReference):
        await repo.save(second)
