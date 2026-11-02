"""Postgres InquiryRepository contract tests."""

from __future__ import annotations

import pytest
from app.store.postgres import PostgresInquiryRepository
from tests.store import test_repository_contract as contract

pytestmark = pytest.mark.postgres


@pytest.fixture
def memory_repo(pg_repo: PostgresInquiryRepository) -> PostgresInquiryRepository:
    return pg_repo


test_create_and_get = contract.test_create_and_get
test_save_bumps_version = contract.test_save_bumps_version
test_save_version_conflict = contract.test_save_version_conflict
test_touch_refreshes_expiry_without_version_bump = (
    contract.test_touch_refreshes_expiry_without_version_bump
)
test_turn_lease_acquire_and_conflict = contract.test_turn_lease_acquire_and_conflict
test_turn_lease_expired_takeover = contract.test_turn_lease_expired_takeover
test_purge_expired_drafts_only = contract.test_purge_expired_drafts_only
test_get_missing = contract.test_get_missing
