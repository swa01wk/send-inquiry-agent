from datetime import UTC, datetime

from app.domain.draft_ops import add_document, new_inquiry_draft, write_fields
from app.domain.models import Blocker, DocType, FieldKey, Phase, Source
from app.domain.rules import can_submit, compute_phase
from tests.domain.conftest import fill_minimal_collectible


def test_can_submit_blocker_order(master):
    draft = new_inquiry_draft()
    blockers = can_submit(draft)
    tokens = [b.token for b in blockers]
    assert tokens[0] == "cr_pending"
    assert "missing_field:company_name" in tokens
    assert "missing_field:contact" in tokens
    assert tokens[-1] == "terms_not_accepted"


def test_can_submit_existing_account():
    draft = new_inquiry_draft()
    draft.cr_status = "existing"
    blockers = can_submit(draft)
    assert blockers[0] == Blocker.cr_existing()


def test_can_submit_unconfirmed_derived(master):
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft, _, _ = write_fields(
        draft,
        [("sales_category", "fashion", Source.DERIVED)],
        master=master,
    )
    tokens = [b.token for b in can_submit(draft)]
    assert "unconfirmed_field:sales_category" in tokens


def test_can_submit_complete_draft(master):
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.otp_verified = True
    draft.terms_accepted = True
    max_bytes = 5 * 1024 * 1024
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    draft, _ = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="1",
        file_name="co.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    draft, _ = add_document(
        draft,
        DocType.BRAND_PROFILE,
        file_id="2",
        file_name="brand.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    assert can_submit(draft) == []


def test_compute_phase_per_state(master):
    draft = new_inquiry_draft()
    assert compute_phase(draft) == Phase.GATE

    draft.cr_status = "existing"
    assert compute_phase(draft) == Phase.EXISTING_ACCOUNT

    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    assert compute_phase(draft) == Phase.COLLECTING

    draft = fill_minimal_collectible(new_inquiry_draft(), master)

    draft.otp_verified = False
    draft.fields[FieldKey.COMPANY_NAME].confirmed = True
    for key in FieldKey:
        field = draft.fields[key]
        if field.source == Source.DERIVED:
            field.confirmed = True
    assert compute_phase(draft) == Phase.VERIFYING

    draft.otp_verified = True
    assert compute_phase(draft) == Phase.DOCUMENTS

    max_bytes = 5 * 1024 * 1024
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    draft, _ = add_document(
        draft,
        DocType.COMPANY_PROFILE,
        file_id="1",
        file_name="co.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    draft, _ = add_document(
        draft,
        DocType.BRAND_PROFILE,
        file_id="2",
        file_name="brand.pdf",
        size_bytes=100,
        max_bytes=max_bytes,
        uploaded_at=ts,
    )
    assert compute_phase(draft) == Phase.REVIEW

    draft.reference = "GEO-STR-123456"
    assert compute_phase(draft) == Phase.SUBMITTED
