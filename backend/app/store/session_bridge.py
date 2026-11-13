"""Map between Session (API) and Inquiry + handle state."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.sessions import Session
from app.store.handle_state import HandleState
from app.store.models import Inquiry, InquiryStatus, SessionState


def session_from_parts(
    *,
    handle_id: str,
    inquiry: Inquiry,
    handle: HandleState,
    last_seen: datetime,
    created_at: datetime,
) -> Session:
    state = inquiry.session_state
    return Session(
        id=handle_id,
        inquiry_id=str(inquiry.id),
        draft=inquiry.draft,
        created_at=created_at,
        last_seen=last_seen,
        cards_shown=inquiry.cards_shown_set(),
        card_counter=inquiry.card_counter,
        confirm_card_keys=dict(inquiry.confirm_card_keys),
        confirm_card_turns=dict(state.confirm_card_turns),
        turn_index=state.turn_index,
        test_scenario=handle.test_scenario,
        script_step=handle.script_step,
        transcript=list(handle.transcript),
        cards=dict(handle.cards),
        inquiry_seq=handle.inquiry_seq,
        form_mode=handle.form_mode,
        mode=handle.mode,
        case_id=inquiry.case_id,
        contacts_draft=list(handle.contacts_draft),
        channel=inquiry.channel,
        created_by=handle.created_by,
        tenant_id=inquiry.tenant_id,
        staff_id=inquiry.staff_id,
        link_sent_to=handle.link_sent_to,
        complete_nonce=handle.complete_nonce,
        closed=handle.closed,
        contact_check=handle.contact_check,
        contact_email=handle.contact_email,
        origin_id=handle.origin_id,
        signatory_answer=handle.signatory_answer,
        _version=inquiry.version,
    )


def apply_session_to_inquiry(session: Session, inquiry: Inquiry) -> Inquiry:
    updated = inquiry.model_copy(deep=True)
    updated.draft = session.draft
    updated.set_cards_shown(session.cards_shown)
    updated.card_counter = session.card_counter
    updated.confirm_card_keys = dict(session.confirm_card_keys)
    updated.channel = session.channel
    updated.case_id = session.case_id
    updated.tenant_id = session.tenant_id
    updated.staff_id = session.staff_id
    updated.session_state = SessionState(
        confirm_card_turns=dict(session.confirm_card_turns),
        turn_index=session.turn_index,
    )
    if (
        session.closed
        and session.closed.startswith("redirected")
        and updated.status in (InquiryStatus.DRAFT, InquiryStatus.PENDING)
        and not session.draft.reference
    ):
        # Sent to sign in (registered CR, or a call-centre caller with a login, §3.4).
        updated.status = InquiryStatus.REDIRECTED
    return updated


def handle_from_session(session: Session) -> HandleState:
    return HandleState(
        transcript=list(session.transcript),
        cards=dict(session.cards),
        inquiry_seq=session.inquiry_seq,
        form_mode=session.form_mode,
        mode=session.mode,
        contacts_draft=list(session.contacts_draft),
        created_by=session.created_by,
        link_sent_to=session.link_sent_to,
        complete_nonce=session.complete_nonce,
        closed=session.closed,
        contact_check=session.contact_check,
        contact_email=session.contact_email,
        origin_id=session.origin_id,
        signatory_answer=session.signatory_answer,
        test_scenario=session.test_scenario,
        script_step=session.script_step,
    )


def inquiry_id_for(session: Session) -> UUID:
    return UUID(session.inquiry_id)


def legacy_inquiry_from_session(session: Session) -> Inquiry:
    status = InquiryStatus.DRAFT
    if session.draft.reference:
        status = InquiryStatus.SUBMITTED
    if session.closed:
        status = InquiryStatus.REDIRECTED
    return Inquiry(
        id=UUID(session.inquiry_id or session.id),
        status=status,
        draft=session.draft,
        cards_shown=sorted(session.cards_shown),
        confirm_card_keys=dict(session.confirm_card_keys),
        card_counter=session.card_counter,
        reference=None if session.case_id else session.draft.reference,
        version=session._version,
        created_at=session.created_at,
        updated_at=session.last_seen,
        last_seen_at=session.last_seen,
        expires_at=session.last_seen,
        channel=session.channel,
        case_id=session.case_id,
        tenant_id=session.tenant_id,
        staff_id=session.staff_id,
        session_state=SessionState(
            confirm_card_turns=dict(session.confirm_card_turns),
            turn_index=session.turn_index,
        ),
    )
