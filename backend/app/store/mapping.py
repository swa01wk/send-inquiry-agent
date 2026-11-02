"""Map between ORM rows and Inquiry models."""

from __future__ import annotations

from app.domain.models import InquiryDraft
from app.store.models import Inquiry, InquiryStatus, SessionState
from app.store.tables import InquiryRow


def inquiry_from_row(row: InquiryRow) -> Inquiry:
    return Inquiry(
        id=row.id,
        status=InquiryStatus(row.status),
        draft=InquiryDraft.model_validate(row.draft),
        cards_shown=list(row.cards_shown or []),
        confirm_card_keys=dict(row.confirm_card_keys or {}),
        card_counter=int(row.card_counter),
        submit_key=row.submit_key,
        reference=row.reference,
        version=int(row.version),
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_seen_at=row.last_seen_at,
        expires_at=row.expires_at,
        channel=row.channel,
        case_id=row.case_id,
        tenant_id=row.tenant_id,
        staff_id=row.staff_id,
        session_state=SessionState.model_validate(row.session_state or {}),
    )


def row_values_from_inquiry(inquiry: Inquiry) -> dict:
    reference = inquiry.reference or inquiry.draft.reference
    return {
        "status": inquiry.status.value,
        "draft": inquiry.draft.model_dump(mode="json"),
        "cards_shown": list(inquiry.cards_shown),
        "confirm_card_keys": dict(inquiry.confirm_card_keys),
        "card_counter": inquiry.card_counter,
        "submit_key": inquiry.submit_key,
        "reference": reference,
        "version": inquiry.version,
        "updated_at": inquiry.updated_at,
        "last_seen_at": inquiry.last_seen_at,
        "expires_at": inquiry.expires_at,
        "channel": inquiry.channel,
        "case_id": inquiry.case_id,
        "tenant_id": inquiry.tenant_id,
        "staff_id": inquiry.staff_id,
        "session_state": inquiry.session_state.model_dump(mode="json"),
    }
