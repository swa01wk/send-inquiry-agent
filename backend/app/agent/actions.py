"""UI actions handled before the agent graph runs (spec section 4)."""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import HumanMessage

from app.agent.channels import attach_documents_on_file, started_by_label
from app.agent.context import message_context
from app.agent.cr_check import (
    CustomerCheck,
    apply_cr_result,
    check_existing_customer,
    skip_customer_check,
)
from app.agent.cr_question import apply_cr_answer, cr_question_active
from app.agent.events import SseEvent
from app.agent.handoff import start_handoff
from app.agent.pending import RESUME_PENDING_REPLY, normalise_email, note_verification
from app.agent.runtime import AgentRuntime
from app.api.cards import (
    HANDOFF_CARD_ID,
    allocate_confirm_card_id,
    build_confirm_fields_card,
    build_document_upload_card,
    build_review_card,
    build_success_card,
    build_terms_card,
    parse_doc_type,
    remember_confirm_card_keys,
    split_card_id,
)
from app.api.case_cards import (
    SignatoryAnswer,
    as_signatory_answer,
    build_case_status_card,
    build_contacts_card,
    build_reupload_card,
    build_signatory_question_card,
    replaced_since,
)
from app.api.channel_cards import (
    BASIC_INFO_CARD_ID,
    build_basic_info_card,
    build_cr_question_card,
    build_existing_cr_choice_card,
    build_send_link_card,
    build_sign_in_prompt_card,
    confirm_basic_info,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.document_checks import document_mismatches
from app.domain.fields import document_definitions
from app.domain.models import NEEDS_CONFIRMATION, DocType, FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit, contact_verified, open_fields, remaining_steps
from app.domain.summary import build_draft_summary
from app.domain.tenant_prefill import prefill_from_tenant
from app.domain.validation import validate_malls
from app.gateway import GatewayError
from app.security import tokens
from app.sessions import Session
from app.workflow.contacts import apply_signatory_answer, confirm_contacts, contacts_blockers
from app.workflow.flow import FlowNode, record_flow_step
from app.workflow.machine import USER, IllegalTransition
from app.workflow.models import Case, TenantContact, WorkflowEvent
from app.workflow.service import apply_event, create_case

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    note: HumanMessage
    events: list[SseEvent] = field(default_factory=list)
    changed_keys: list[str] = field(default_factory=list)
    # Quiet: the card already shows the outcome (a wrong code, a resend, one channel of
    # two verified), so no agent turn runs and no reply is added (spec §6, card actions).
    quiet: bool = False
    # A fixed reply instead of an agent turn (flow v2 `resume_pending`: the same words
    # whether or not an inquiry exists, and the email never reaches the model).
    reply: str | None = None


_SETTABLE_DOCUMENT_NUMBER_KEYS = frozenset(
    {
        FieldKey.VAT_NUMBER.value,
        FieldKey.NATIONAL_ID_NUMBER.value,
        FieldKey.NATIONAL_ADDRESS.value,
    }
)


def _draft_event(draft: InquiryDraft, runtime: AgentRuntime, changed_keys: list[str]) -> SseEvent:
    summary = build_draft_summary(draft, runtime.master, changed_keys)
    return SseEvent(event="draft", data=summary.model_dump())


def _card_event(session: Session, card: UiCard) -> SseEvent:
    remember_confirm_card_keys(session, card)
    return SseEvent(event="ui_card", data=card.model_dump())


def _review_refresh(session: Session, draft: InquiryDraft, runtime: AgentRuntime) -> list[SseEvent]:
    """The review card shows a snapshot of the draft. Once it's on screen, a change made on
    another card (or on the review card itself) re-sends it, same card id, updated in place
    (re-demo flow 3, 10 Nov: rent and lease edits left it showing "Not yet collected")."""
    shown = session.cards.get("review")
    if not shown:
        return []
    card = build_review_card(draft, runtime.master, message_id=shown.get("message_id"))
    return [_card_event(session, card)]


async def handle_ui_action(
    action: str,
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    handlers = {
        "select_malls": _select_malls,
        "verify_email": _verify_email,
        "resend_email_link": _resend_email_link,
        "submit_otp": _submit_otp,
        "resend_otp": _resend_otp,
        "edit_field": _edit_field,
        "confirm_card": _confirm_card,
        "accept_and_submit": _accept_and_submit,
        "documents_updated": _documents_updated,
        "set_document_number": _set_document_number,
        "request_handoff": _request_handoff,
        "cr_check": _cr_check,
        "cr_skip": _cr_skip,
        "cr_answer": _cr_answer,
        # Flow v2 (§3.3)
        "accept_terms": _accept_terms,
        "resume_pending": _resume_pending,
        "resubmit_documents": _resubmit_documents,
        "submit_contacts": _submit_contacts,
        "signatory_answer": _signatory_answer,
        "submit_sales_data": _submit_sales_data,
        # Intake channels (spec §15)
        "send_application_link": _send_application_link,
        "existing_cr_choice": _existing_cr_choice,
        "proceed_basic_info": _proceed_basic_info,
    }
    handler = handlers.get(action)
    if handler is None:
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] unknown_action {action}"),
        )
    return await handler(payload, session, runtime)


async def _select_malls(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    mall_ids = payload.get("mall_ids")
    if not isinstance(mall_ids, list):
        return ActionResult(note=HumanMessage(content="[ui_event] malls_invalid"))
    checked = validate_malls(mall_ids, runtime.master)
    if isinstance(checked, v.ValidationError):
        return ActionResult(note=HumanMessage(content=f"[ui_event] malls_invalid {checked.code}"))
    draft, written, errors = draft_ops.write_fields(
        session.draft,
        [(FieldKey.MALLS.value, checked, Source.USER)],
        master=runtime.master,
    )
    if errors:
        return ActionResult(note=HumanMessage(content="[ui_event] malls_invalid"))
    session.draft = draft
    names = [runtime.master.label_for("malls", mall_id) or mall_id for mall_id in checked]
    note = HumanMessage(content=f"[ui_event] malls_selected: {', '.join(names)}")
    return ActionResult(
        note=note,
        events=[_draft_event(draft, runtime, written)],
        changed_keys=written,
    )


def _verification_note(event: str, draft: InquiryDraft) -> HumanMessage:
    """`[ui_event] <event>` plus whether the contact is now fully verified, and whether the
    required documents are already in (the upload path sends them first: re-demo flow 1,
    10 Nov), so the agent doesn't show and list the documents again."""
    tail = ""
    if contact_verified(draft):
        tail = " verification_complete"
        if "documents" not in remaining_steps(draft):
            tail += " documents_complete"
    return HumanMessage(content=f"[ui_event] {event}{tail}")


def _verification_events(
    session: Session,
    draft: InquiryDraft,
    runtime: AgentRuntime,
    changed_keys: list[str],
) -> list[SseEvent]:
    card = runtime.verification_card(draft, session.id)
    return [_card_event(session, card), _draft_event(draft, runtime, changed_keys)]


def _audit(
    runtime: AgentRuntime,
    session: Session,
    event: str,
    *,
    by_staff: bool = False,
    **payload: object,
) -> None:
    actor: Literal["staff", "user"] = "staff" if by_staff else "user"
    runtime.services.audit.record(session.id, event, actor=actor, payload=dict(payload))


def _throttled(
    runtime: AgentRuntime,
    session: Session,
    channel: str,
    *,
    quiet: bool = False,
) -> ActionResult | None:
    wait = runtime.services.resend.wait_seconds(session.id, channel)  # type: ignore[arg-type]
    if not wait:
        return None
    _audit(runtime, session, "verification_sent", channel=channel, result="throttled")
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] resend_throttled {wait}"),
        events=_verification_events(session, session.draft, runtime, []),
        quiet=quiet,
    )


async def _verify_email(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """The user followed the emailed link (in the POC, the card's demo button)."""
    token = str(payload.get("token", ""))
    draft = session.draft.model_copy(deep=True)
    try:
        check = await runtime.services.gateway.call(
            "email",
            "verify",
            runtime.services.email_verification.verify,
            session.id,
            token,
            inquiry_id=session.id,
        )
    except GatewayError as err:
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] {err.note}"),
            events=_verification_events(session, draft, runtime, []),
        )
    current = draft.fields[FieldKey.EMAIL].value
    if check.verified_email is None or check.verified_email != current:
        _audit(runtime, session, "verification_result", channel="email", result="invalid")
        note_verification(
            runtime.services.audit,
            inquiry_id=session.id,
            draft=draft,
            verified_before=False,
            succeeded=False,
        )
        return ActionResult(
            note=HumanMessage(content="[ui_event] email_link_invalid"),
            events=_verification_events(session, draft, runtime, []),
        )
    verified_before = contact_verified(draft)
    draft.email_verified = True
    draft_ops.stamp_verified(draft)
    session.draft = draft
    _audit(runtime, session, "verification_result", channel="email", result="verified")
    note_verification(
        runtime.services.audit,
        inquiry_id=session.id,
        draft=draft,
        verified_before=verified_before,
        succeeded=True,
        channel=session.channel,
    )
    return ActionResult(
        note=_verification_note("email_verified", draft),
        events=_verification_events(session, draft, runtime, ["email_verified"]),
        changed_keys=["email_verified"],
        # One channel of two: the card shows the tick; the agent speaks when both are done.
        quiet=not contact_verified(draft),
    )


async def _resend_email_link(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    del payload
    draft = session.draft.model_copy(deep=True)
    email = draft.fields[FieldKey.EMAIL].value
    if not email:
        return ActionResult(note=HumanMessage(content="[ui_event] email_link_blocked no_email"))
    if (throttled := _throttled(runtime, session, "email", quiet=True)) is not None:
        return throttled
    try:
        await runtime.services.gateway.call(
            "email",
            "send_link",
            runtime.services.email_verification.send_link,
            session.id,
            str(email),
            message_context(draft, runtime.master),
            inquiry_id=session.id,
        )
    except GatewayError as err:
        _audit(runtime, session, "verification_sent", channel="email", result=err.kind)
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] {err.note}"),
            events=_verification_events(session, draft, runtime, []),
        )
    runtime.services.resend.record(session.id, "email")
    _audit(runtime, session, "verification_sent", channel="email", result="sent")
    draft.email_link_sent_to = str(email)
    session.draft = draft
    return ActionResult(
        note=HumanMessage(content="[ui_event] email_link_resent"),
        events=_verification_events(session, draft, runtime, []),
        quiet=True,
    )


async def _submit_otp(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Mobile OTP. The code never reaches the LLM; only the outcome does."""
    code = v.normalise_digits(str(payload.get("code", ""))).strip()
    draft = session.draft.model_copy(deep=True)
    mobile = draft.fields[FieldKey.MOBILE].value
    if not mobile or draft.otp_sent_to != str(mobile):
        return ActionResult(note=HumanMessage(content="[ui_event] otp_not_sent"))
    try:
        verified = await runtime.services.gateway.call(
            "otp",
            "verify",
            runtime.services.otp.verify,
            session.id,
            code,
            inquiry_id=session.id,
        )
    except GatewayError as err:
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] {err.note}"),
            events=_verification_events(session, draft, runtime, []),
        )

    if verified:
        verified_before = contact_verified(draft)
        draft.mobile_verified = True
        draft_ops.stamp_verified(draft)
        session.draft = draft
        _audit(runtime, session, "verification_result", channel="sms", result="verified")
        note_verification(
            runtime.services.audit,
            inquiry_id=session.id,
            draft=draft,
            verified_before=verified_before,
            succeeded=True,
            channel=session.channel,
        )
        return ActionResult(
            note=_verification_note("mobile_verified", draft),
            events=_verification_events(session, draft, runtime, ["mobile_verified"]),
            changed_keys=["mobile_verified"],
            quiet=not contact_verified(draft),
        )

    _audit(runtime, session, "verification_result", channel="sms", result="wrong_code")
    note_verification(
        runtime.services.audit,
        inquiry_id=session.id,
        draft=draft,
        verified_before=False,
        succeeded=False,
    )
    draft.otp_attempts_left = max(0, draft.otp_attempts_left - 1)
    if draft.otp_attempts_left <= 0:
        session.draft = draft
        if (throttled := _throttled(runtime, session, "sms")) is not None:
            return throttled
        try:
            await runtime.services.gateway.call(
                "otp",
                "send",
                runtime.services.otp.send,
                session.id,
                str(mobile),
                message_context(draft, runtime.master),
                inquiry_id=session.id,
            )
        except GatewayError as err:
            return ActionResult(
                note=HumanMessage(content=f"[ui_event] {err.note}"),
                events=_verification_events(session, draft, runtime, []),
            )
        runtime.services.resend.record(session.id, "sms")
        _audit(runtime, session, "verification_sent", channel="sms", result="sent")
        draft.otp_attempts_left = 3
        session.draft = draft
        return ActionResult(
            note=HumanMessage(content="[ui_event] otp_resent"),
            events=_verification_events(session, draft, runtime, ["otp_attempts_left"]),
            changed_keys=["otp_attempts_left"],
        )

    session.draft = draft
    return ActionResult(
        note=HumanMessage(
            content=f"[ui_event] otp_failed attempts_left={draft.otp_attempts_left}",
        ),
        events=_verification_events(session, draft, runtime, ["otp_attempts_left"]),
        changed_keys=["otp_attempts_left"],
        quiet=True,
    )


async def _resend_otp(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    del payload
    draft = session.draft.model_copy(deep=True)
    mobile = draft.fields[FieldKey.MOBILE].value
    if not mobile:
        return ActionResult(
            note=HumanMessage(content="[ui_event] otp_send_blocked no_mobile"),
        )
    if (throttled := _throttled(runtime, session, "sms", quiet=True)) is not None:
        return throttled
    try:
        await runtime.services.gateway.call(
            "otp",
            "send",
            runtime.services.otp.send,
            session.id,
            str(mobile),
            message_context(draft, runtime.master),
            inquiry_id=session.id,
        )
    except GatewayError as err:
        _audit(runtime, session, "verification_sent", channel="sms", result=err.kind)
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] {err.note}"),
            events=_verification_events(session, draft, runtime, []),
        )
    runtime.services.resend.record(session.id, "sms")
    _audit(runtime, session, "verification_sent", channel="sms", result="sent")
    draft.otp_sent_to = str(mobile)
    draft.otp_attempts_left = 3
    session.draft = draft
    return ActionResult(
        note=HumanMessage(content="[ui_event] otp_resent"),
        events=_verification_events(session, draft, runtime, ["otp_attempts_left"]),
        changed_keys=["otp_attempts_left"],
        quiet=True,
    )


async def _edit_field(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    key = payload.get("key")
    value = payload.get("value")
    if not isinstance(key, str):
        return ActionResult(note=HumanMessage(content="[ui_event] field_edit_failed"))
    # An executive editing for a caller writes `staff`; the applicant writes `user`.
    source = Source.STAFF if session.assisted else Source.USER
    draft, written, errors = draft_ops.write_fields(
        session.draft,
        [(key, value, source)],
        master=runtime.master,
    )
    if errors or not written:
        return ActionResult(note=HumanMessage(content=f"[ui_event] field_edit_failed {key}"))
    session.draft = draft
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] field_edited {key}"),
        events=[_draft_event(draft, runtime, written), *_review_refresh(session, draft, runtime)],
        changed_keys=written,
    )


async def _confirm_card(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    raw_card_id = payload.get("card_id")
    if not isinstance(raw_card_id, str):
        return ActionResult(note=HumanMessage(content="[ui_event] confirm_failed"))
    card_id, card_seq = split_card_id(raw_card_id)
    if card_seq != session.inquiry_seq:
        # A card from an earlier inquiry in this chat (follow-on): it can't change this one.
        return ActionResult(note=HumanMessage(content="[ui_event] confirm_failed stale_card"))
    listed = session.confirm_card_keys.get(card_id)
    if not listed:
        return ActionResult(note=HumanMessage(content="[ui_event] confirm_failed"))
    keys: list[str] = []
    for key_str in listed:
        try:
            field_key = FieldKey(key_str)
        except ValueError:
            continue
        field = session.draft.fields[field_key]
        if field.value is None:
            continue
        if field.source in NEEDS_CONFIRMATION and not field.confirmed:
            keys.append(key_str)
    if not keys:
        # Everything on the card is already confirmed (often the agent confirmed it from
        # the user's "yes" a moment earlier). Not a failure: refresh the card and say so.
        card = build_confirm_fields_card(session.draft, runtime.master, listed, card_id=card_id)
        return ActionResult(
            note=HumanMessage(content="[ui_event] fields_already_confirmed"),
            events=[_card_event(session, card)],
        )
    draft = draft_ops.confirm(session.draft, keys)
    session.draft = draft
    events: list[SseEvent] = [_draft_event(draft, runtime, keys)]
    card = build_confirm_fields_card(draft, runtime.master, listed, card_id=card_id)
    events.append(_card_event(session, card))
    events.extend(_review_refresh(session, draft, runtime))
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] fields_confirmed {' '.join(keys)}"),
        events=events,
        changed_keys=keys,
    )


def document_review_notes(
    session: Session, runtime: AgentRuntime, doc_type: DocType | None
) -> list[str]:
    """What a profile upload changed (demo feedback §3.7), as field names only: never a
    value from the document (ADR-R5)."""
    if doc_type is None:
        return []
    ref = session.draft.documents.get(doc_type)
    if ref is None:
        return []
    notes: list[str] = []
    if ref.filled_fields:
        notes.append(
            f"[ui_event] document_fields {doc_type.value} filled={','.join(ref.filled_fields)}"
        )
    for mismatch in document_mismatches(session.draft, runtime.master, doc_type=doc_type):
        # R4: a signed-in tenant's company comes from Cenomi's record (Yardi), not from what
        # they typed, so the agent names the record instead.
        field = session.draft.fields[FieldKey(mismatch.field)]
        source = " source=cenomi_record" if field.source == Source.VERIFIED else ""
        notes.append(f"[ui_event] document_mismatch {mismatch.field}{source}")
    return notes


def _still_needed_tokens(draft: InquiryDraft) -> list[str]:
    """What's open besides documents and terms, with the `fields` step as field keys (e.g.
    `brand_name_ar`), so the agent asks for a field instead of guessing a card."""
    tokens: list[str] = []
    for step in remaining_steps(draft):
        if step in ("documents", "terms"):
            continue
        if step == "fields":
            missing, unconfirmed = open_fields(draft)
            tokens.extend(missing)
            tokens.extend(f"confirm:{key}" for key in unconfirmed)
            continue
        tokens.append(step)
    return tokens


async def _documents_updated(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    draft = session.draft
    # Optional `doc_type`: the profile just uploaded, sent when it filled a field or
    # disagrees with one (UploadDocumentResponse.fields_filled / mismatches).
    uploaded = parse_doc_type(str(payload.get("doc_type") or ""))
    review_notes = document_review_notes(session, runtime, uploaded)
    pending = [
        doc_type.value
        for doc_type, _label, required in document_definitions()
        if required and doc_type not in draft.documents
    ]
    if not pending:
        # Documents can come before verification; say what's still open so the agent
        # doesn't point to Submit too early.
        left = _still_needed_tokens(draft)
        tail = f" still_needed={','.join(left)}" if left else ""
        status = f"[ui_event] documents_complete{tail}"
    else:
        status = f"[ui_event] documents_pending {' '.join(pending)}"
    events: list[SseEvent] = []
    # Values a profile filled are confirmed on a card like any derived value (golden rule
    # 2); the upload itself (REST) shows no card, so it's shown here, as for a CR prefill.
    ref = draft.documents.get(uploaded) if uploaded is not None else None
    to_confirm = [
        key
        for key in (ref.filled_fields if ref else [])
        if not draft.fields[FieldKey(key)].confirmed
    ]
    if to_confirm:
        card_id = allocate_confirm_card_id(sorted(session.cards_shown))
        session.cards_shown.add(card_id)
        card = build_confirm_fields_card(
            draft,
            runtime.master,
            to_confirm,
            card_id=card_id,
            title="From your profile — please confirm",
        )
        events.append(_card_event(session, card))
    events.extend(_review_refresh(session, draft, runtime))
    return ActionResult(
        note=HumanMessage(content="\n".join([*review_notes, status])),
        events=events,
    )


async def _set_document_number(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    key = payload.get("key")
    value = payload.get("value")
    if not isinstance(key, str) or not isinstance(value, str):
        return ActionResult(note=HumanMessage(content="[ui_event] document_number_invalid"))
    if key not in _SETTABLE_DOCUMENT_NUMBER_KEYS:
        if key == FieldKey.CR_NUMBER.value:
            code = "read_only"
        else:
            code = "unknown_field"
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] document_number_invalid {key} {code}"),
        )
    draft, written, errors = draft_ops.write_fields(
        session.draft,
        [(key, value, Source.USER)],
        master=runtime.master,
    )
    field_err = errors.get(key)
    if field_err is not None:
        card = build_document_upload_card(
            session.draft,
            runtime.master,
            max_mb=runtime.settings.max_upload_mb,
            number_errors={key: field_err.message},
        )
        return ActionResult(
            note=HumanMessage(
                content=f"[ui_event] document_number_invalid {key} {field_err.code}",
            ),
            events=[_card_event(session, card)],
        )
    session.draft = draft
    # Re-send the card without errors so an earlier error on this row clears.
    card = build_document_upload_card(
        draft,
        runtime.master,
        max_mb=runtime.settings.max_upload_mb,
    )
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] document_number_set {key}"),
        events=[_card_event(session, card), _draft_event(draft, runtime, written)],
        changed_keys=written,
        quiet=True,
    )


async def _accept_and_submit(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    # Flow v2 (FV15): the terms were accepted on their own card; Submit still needs them.
    accepted = payload.get("terms_accepted") is True or (
        session.draft.intake_flow == "v2" and session.draft.terms_accepted
    )
    if not accepted:
        return ActionResult(
            note=HumanMessage(content="[ui_event] submit_blocked terms_not_accepted"),
        )
    submit_key = submit_idempotency_key(session)

    # Submit once (M0 §7.2 at Day 2 depth): a second press shows the same reference.
    if session.draft.reference:
        reference = session.draft.reference
        _audit(
            runtime,
            session,
            "submit_result",
            submit_key=submit_key,
            outcome="submitted",
            reference=reference,
            repeat=True,
        )
        success = build_success_card(
            reference, tracking_url=tracking_url(runtime, session.id, reference)
        )
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] submitted reference={reference} (repeat)"),
            events=[_card_event(session, success)],
        )

    draft = session.draft.model_copy(deep=True)
    draft.terms_accepted = True
    blockers = can_submit(draft)
    if blockers:
        session.draft = draft
        card = build_review_card(draft, runtime.master)
        if "review" not in session.cards_shown:
            session.cards_shown.add("review")
        tokens_text = " ".join(b.token for b in blockers)
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] submit_blocked {tokens_text}"),
            events=[_card_event(session, card), _draft_event(draft, runtime, ["terms_accepted"])],
            changed_keys=["terms_accepted"],
        )

    _audit(runtime, session, "submit_attempt", submit_key=submit_key, outcome="sent")
    try:
        reference = runtime.services.gateway.call_sync(
            "submit",
            "submit",
            runtime.services.submit.submit,
            draft,
            runtime.master,
            idempotency_key=submit_key,
            inquiry_id=session.id,
        )
    except GatewayError as err:
        # Nothing is lost: the same key returns the same reference when Submit is pressed
        # again. Rejected = a definite no; timeout or unavailable = try again shortly.
        session.draft = draft
        outcome = "submit_failed" if err.kind in ("rejected", "invalid") else "submit_pending"
        _audit(runtime, session, "submit_result", submit_key=submit_key, outcome=err.kind)
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] {outcome} {err.kind}"),
            events=[_draft_event(draft, runtime, ["terms_accepted"])],
            changed_keys=["terms_accepted"],
        )

    draft.reference = reference
    session.draft = draft
    _audit(
        runtime,
        session,
        "submit_result",
        submit_key=submit_key,
        outcome="submitted",
        reference=reference,
        repeat=False,
    )
    link = tracking_url(runtime, session.id, reference)
    await _send_submission_notices(runtime, session, draft, reference, link)
    # Flow v2 §3.1: "Complete form and submit" → "Reference No." on the chart, recorded on
    # the case id (the reference) before the case's own steps.
    submitter: Literal["staff", "user"] = "staff" if session.created_by else "user"
    record_flow_step(runtime, inquiry_id=reference, node=FlowNode.COMPLETE1, actor=submitter)
    record_flow_step(runtime, inquiry_id=reference, node=FlowNode.REF1)
    # The review lifecycle starts (L4): the case is created and routed to its queue.
    try:
        await create_case(
            runtime,
            session_id=session.id,
            inquiry_seq=session.inquiry_seq,
            draft=draft,
            reference=reference,
            channel=session.channel,
            created_by=session.created_by,
            tenant_id=session.tenant_id,
        )
    except Exception:  # the submission stands; the case can be created again on retry
        logger.exception("case creation failed for %s", reference)
    success = build_success_card(reference, tracking_url=link)
    session.cards_shown.add("success")
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] submitted reference={reference}"),
        events=[
            _card_event(session, success),
            _draft_event(draft, runtime, ["reference", "terms_accepted"]),
        ],
        changed_keys=["reference", "terms_accepted"],
    )


async def _cr_check(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """The CR check from a card (form mode, L3 §3.14): same rules as the `verify_cr` tool.
    Flow v2 (§3.2): the Company Registration card's Verify."""
    if session.draft.intake_flow == "v2" and not session.assisted:
        check = check_existing_customer(session, runtime, str(payload.get("cr_number", "")))
        checked = customer_check_result(session, runtime, check)
        # A wrong number or a service error: the card shows it; no agent turn (S5).
        checked.quiet = check.note.startswith(("[ui_event] cr_invalid", "[ui_event] service_error"))
        return checked
    if cr_question_active(
        assisted=session.assisted, channel=session.channel, test_scenario=session.test_scenario
    ):
        # Demo feedback §3.1: the public page never looks a CR up.
        return ActionResult(note=HumanMessage(content="[ui_event] cr_lookup_off"))
    validated = v.validate_cr_number(str(payload.get("cr_number", "")))
    if isinstance(validated, v.ValidationError):
        return ActionResult(note=HumanMessage(content=f"[ui_event] cr_invalid {validated.code}"))
    if session.draft.cr_status != "unknown":
        return ActionResult(note=HumanMessage(content="[ui_event] cr_already_done"))
    try:
        result = runtime.services.gateway.call_sync(
            "cr", "verify", runtime.services.cr.verify, validated, inquiry_id=session.id
        )
    except GatewayError as err:
        return ActionResult(note=HumanMessage(content=f"[ui_event] {err.note}"))
    outcome = apply_cr_result(session.draft, validated, result, runtime.master)
    if outcome.errors:
        return ActionResult(note=HumanMessage(content="[ui_event] cr_invalid prefill_error"))
    session.draft = outcome.draft
    events: list[SseEvent] = [_draft_event(outcome.draft, runtime, outcome.changed)]
    if outcome.confirm_keys:
        card_id = allocate_confirm_card_id(sorted(session.cards_shown))
        session.cards_shown.add(card_id)
        card = build_confirm_fields_card(
            outcome.draft,
            runtime.master,
            outcome.confirm_keys,
            card_id=card_id,
            title="From your CR — please confirm",
        )
        events.append(_card_event(session, card))
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] cr_checked {outcome.kind}"),
        events=events,
        changed_keys=outcome.changed,
    )


async def _cr_skip(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    if session.draft.intake_flow == "v2" and not session.assisted:
        # Flow v2 (§3.2): Skip asks "Are you sure…?" first; only the confirmed skip counts.
        confirmed = payload.get("confirmed") is True
        skipped = customer_check_result(
            session, runtime, skip_customer_check(session, runtime, confirmed=confirmed)
        )
        skipped.quiet = not confirmed
        return skipped
    if session.draft.cr_status != "unknown":
        return ActionResult(note=HumanMessage(content="[ui_event] cr_already_done"))
    draft = session.draft.model_copy(deep=True)
    draft.cr_status = "skipped"
    session.draft = draft
    return ActionResult(
        note=HumanMessage(content="[ui_event] cr_skipped"),
        events=[_draft_event(draft, runtime, ["cr_status"])],
        changed_keys=["cr_status"],
    )


async def _resume_pending(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Flow v2 "Continue my inquiry" (§3.3, FV13). The email comes from the card, never the
    model. A pending inquiry for it (verified, not submitted, within the TTL) gets a
    `resume_link` email that re-verifies the address and resumes that chat. The reply is the
    same either way, so the answer says nothing about who has an inquiry."""
    from app.store.purge import expire_pending_inquiries

    email = normalise_email(payload.get("email"))
    found = None
    if email and runtime.repo is not None:
        await expire_pending_inquiries(runtime.repo)
        found = await runtime.repo.pending_by_email(email)
    if found is not None:
        pending_id = str(found.id)
        resend = runtime.services.resend
        # Its own limit: the verification email sent minutes earlier mustn't hold it back.
        throttle_key = f"{pending_id}:resume"
        if not resend.wait_seconds(throttle_key, "email"):
            try:
                await runtime.services.gateway.call(
                    "email",
                    "send_link",
                    runtime.services.email_verification.send_link,
                    pending_id,
                    # As saved: the link checks it against the inquiry's email.
                    str(found.draft.fields[FieldKey.EMAIL].value),
                    message_context(found.draft, runtime.master),
                    inquiry_id=pending_id,
                    template="resume_link",
                )
                resend.record(throttle_key, "email")
            except GatewayError:
                logger.warning("resume link not sent for a pending inquiry")
    _audit(runtime, session, "pending_resume_requested", found=found is not None)
    return ActionResult(
        note=HumanMessage(content="[ui_event] resume_pending_requested"),
        reply=RESUME_PENDING_REPLY,
    )


async def _accept_terms(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Flow v2 terms before documents (§3.3, FV15): the terms card's checkbox."""
    if payload.get("terms_accepted") is not True:
        return ActionResult(note=HumanMessage(content="[ui_event] terms_not_accepted"))
    draft = session.draft.model_copy(deep=True)
    draft.terms_accepted = True
    session.draft = draft
    _audit(runtime, session, "terms_accepted", channel=session.channel)
    events = [
        _card_event(session, build_terms_card(draft)),
        _draft_event(draft, runtime, ["terms_accepted"]),
        *_review_refresh(session, draft, runtime),
    ]
    return ActionResult(
        note=HumanMessage(content="[ui_event] terms_accepted"),
        events=events,
        changed_keys=["terms_accepted"],
    )


def customer_check_result(
    session: Session, runtime: AgentRuntime, check: CustomerCheck
) -> ActionResult:
    """A flow v2 Company Registration outcome as card events and the agent's note."""
    events: list[SseEvent] = [_card_event(session, check.card)]
    if check.sign_in is not None:
        events.append(_card_event(session, check.sign_in))
    if check.changed:
        events.append(_draft_event(session.draft, runtime, check.changed))
    return ActionResult(
        note=HumanMessage(content=check.note), events=events, changed_keys=check.changed
    )


def cr_answer_result(session: Session, runtime: AgentRuntime, has_cr: bool) -> ActionResult:
    """ "Do you have a CR?" answered (demo feedback §3.1). Yes: the sign-in card and no more
    collection; No: carry on in chat. Shared by the `cr_answer` card action and a CR number
    typed in the public chat (it's never saved or checked)."""
    if not cr_question_active(
        assisted=session.assisted, channel=session.channel, test_scenario=session.test_scenario
    ):
        return ActionResult(note=HumanMessage(content="[ui_event] cr_answer_off"))
    answered = apply_cr_answer(session.draft, has_cr)
    if answered is None:
        return ActionResult(note=HumanMessage(content="[ui_event] cr_already_done"))
    session.draft = answered.draft
    card = build_cr_question_card(answered="yes" if has_cr else "no")
    events: list[SseEvent] = [_card_event(session, card)]
    if has_cr:
        session.closed = "redirected_to_sign_in"
        _audit(runtime, session, "inquiry_redirected", reason="has_cr", channel=session.channel)
        events.append(
            _card_event(
                session,
                build_sign_in_prompt_card(runtime.settings.public_base_url, reason="has_cr"),
            )
        )
    events.append(_draft_event(answered.draft, runtime, answered.changed))
    return ActionResult(
        note=HumanMessage(content=answered.note),
        events=events,
        changed_keys=answered.changed,
    )


async def _cr_answer(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    has_cr = payload.get("has_cr")
    if not isinstance(has_cr, bool):
        return ActionResult(note=HumanMessage(content="[ui_event] cr_answer_invalid"))
    return cr_answer_result(session, runtime, has_cr)


# ---- Case actions (after submission, L4 §3.5): the applicant answers a request -------


def _case_for(session: Session, runtime: AgentRuntime) -> Case | None:
    if session.mode != "case" or not session.case_id:
        return None
    return runtime.services.cases.get(session.case_id)


def _case_events(session: Session, runtime: AgentRuntime, case: Case) -> list[SseEvent]:
    return [_card_event(session, build_case_status_card(case))]


async def _apply_user_event(
    runtime: AgentRuntime, case: Case, name: str, payload: dict[str, Any]
) -> tuple[Case | None, str | None]:
    try:
        updated = await apply_event(
            runtime, case.id, WorkflowEvent(name=name, payload=payload), USER
        )
    except IllegalTransition as exc:
        return None, exc.message
    return updated, None


async def _resubmit_documents(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Every requested document replaced after the request → `documents_resubmitted`."""
    del payload
    case = _case_for(session, runtime)
    request = case.open_request("reupload") if case else None
    if case is None or request is None:
        return ActionResult(note=HumanMessage(content="[ui_event] resubmit_blocked no_request"))
    missing = [
        d.value
        for d in request.doc_types
        if not replaced_since(session.draft, d, request.requested_at)
    ]
    if missing:
        card = build_reupload_card(
            session.draft, request, runtime.master, max_mb=runtime.settings.max_upload_mb
        )
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] resubmit_blocked {' '.join(missing)}"),
            events=[_card_event(session, card)],
        )
    documents = {
        d.value: session.draft.documents[d].model_dump(mode="json") for d in request.doc_types
    }
    updated, error = await _apply_user_event(
        runtime, case, "documents_resubmitted", {"documents": documents}
    )
    if updated is None:
        return ActionResult(note=HumanMessage(content=f"[ui_event] resubmit_blocked {error}"))
    return ActionResult(
        note=HumanMessage(content="[ui_event] documents_resubmitted"),
        events=_case_events(session, runtime, updated),
    )


async def _submit_contacts(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Send contacts: pressing Send on the contacts card accepts what it shows (each value
    was on the card), then the required roles are checked → `contacts_provided`."""
    del payload
    case = _case_for(session, runtime)
    request = case.open_request("contacts") if case else None
    if case is None or request is None:
        return ActionResult(note=HumanMessage(content="[ui_event] contacts_blocked no_request"))
    contacts = confirm_contacts([TenantContact.model_validate(c) for c in session.contacts_draft])
    blockers = contacts_blockers(contacts)
    if blockers:
        card = build_contacts_card(contacts, request, case=case, signatory_answer=_answer(session))
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] contacts_blocked {' '.join(blockers)}"),
            events=[_card_event(session, card)],
        )
    updated, error = await _apply_user_event(
        runtime,
        case,
        "contacts_provided",
        {"contacts": [c.model_dump(mode="json") for c in contacts]},
    )
    if updated is None:
        return ActionResult(note=HumanMessage(content=f"[ui_event] contacts_blocked {error}"))
    session.contacts_draft = [c.model_dump(mode="json") for c in contacts]
    return ActionResult(
        note=HumanMessage(content="[ui_event] contacts_submitted"),
        events=[
            _card_event(
                session,
                build_contacts_card(
                    contacts, None, case=updated, signatory_answer=_answer(session)
                ),
            ),
            *_case_events(session, runtime, updated),
        ],
    )


def _answer(session: Session) -> SignatoryAnswer | None:
    return as_signatory_answer(session.signatory_answer)


def signatory_answer_result(
    session: Session, runtime: AgentRuntime, is_signatory: bool
) -> ActionResult:
    """ "Are you the authorised signatory?" answered (demo feedback §3.5). Yes: the verified
    primary contact becomes the signatory; No: the card asks for the signatory's details.
    Both refresh the contacts card. Shared by the card action and the case agent's tool."""
    case = _case_for(session, runtime)
    request = case.open_request("contacts") if case else None
    if case is None or request is None:
        return ActionResult(note=HumanMessage(content="[ui_event] signatory_answer no_request"))
    current = [TenantContact.model_validate(c) for c in session.contacts_draft]
    contacts, note = apply_signatory_answer(current, session.draft, is_signatory)
    session.contacts_draft = [c.model_dump(mode="json") for c in contacts]
    session.signatory_answer = "yes" if is_signatory else "no"
    answer = _answer(session)
    _audit(runtime, session, "signatory_answered", answer=session.signatory_answer)
    return ActionResult(
        note=HumanMessage(content=note),
        events=[
            _card_event(session, build_signatory_question_card(answered=answer)),
            _card_event(
                session,
                build_contacts_card(contacts, request, case=case, signatory_answer=answer),
            ),
        ],
    )


async def _signatory_answer(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    is_signatory = payload.get("is_signatory")
    if not isinstance(is_signatory, bool):
        return ActionResult(note=HumanMessage(content="[ui_event] signatory_answer_invalid"))
    return signatory_answer_result(session, runtime, is_signatory)


async def _submit_sales_data(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    del payload
    case = _case_for(session, runtime)
    request = case.open_request("sales_data") if case else None
    if case is None or request is None:
        return ActionResult(note=HumanMessage(content="[ui_event] sales_data_blocked no_request"))
    ref = session.draft.documents.get(DocType.SALES_DATA)
    if ref is None or ref.uploaded_at <= request.requested_at:
        return ActionResult(
            note=HumanMessage(content="[ui_event] sales_data_blocked missing_file"),
        )
    updated, error = await _apply_user_event(
        runtime, case, "sales_data_provided", {"document": ref.model_dump(mode="json")}
    )
    if updated is None:
        return ActionResult(note=HumanMessage(content=f"[ui_event] sales_data_blocked {error}"))
    return ActionResult(
        note=HumanMessage(content="[ui_event] sales_data_submitted"),
        events=_case_events(session, runtime, updated),
    )


def submit_idempotency_key(session: Session) -> str:
    """One key per inquiry: `inq:<session>:v1`, then v2, v3… for follow-on inquiries."""
    return f"inq:{session.id}:v{session.inquiry_seq}"


async def _request_handoff(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Hand the inquiry to a person (L3 §3.6): call-centre case plus the handoff card.

    Needs no model, so form mode's "Ask us to call you" uses it too. The router's
    `human_help` intent can call `handle_ui_action("request_handoff", …)` directly.
    """
    reason = payload.get("reason")
    if reason not in ("user_asked", "model_unavailable"):
        reason = "user_asked"
    recent = [m["text"] for m in session.transcript if m.get("role") == "user"]
    result = await start_handoff(
        session_id=session.id,
        inquiry_seq=session.inquiry_seq,
        draft=session.draft,
        recent_user_messages=recent,
        reason=str(reason),
        runtime=runtime,
    )
    events: list[SseEvent] = []
    if result.card is not None:
        session.cards_shown.add(HANDOFF_CARD_ID)
        events.append(_card_event(session, result.card))
    return ActionResult(note=HumanMessage(content=result.note), events=events)


def tracking_url(runtime: AgentRuntime, session_id: str, reference: str) -> str:
    """Private tracking link: `<PUBLIC_BASE_URL>/inquiry/status/<ref>?t=<track token>`."""
    settings = runtime.settings
    token, _claims = tokens.issue(
        settings.token_secret,
        "track",
        reference,
        ttl_seconds=settings.track_ttl_days * 86400,
        data={"i": session_id},
    )
    return f"{settings.public_base_url.rstrip('/')}/inquiry/status/{reference}?t={token}"


async def _send_submission_notices(
    runtime: AgentRuntime,
    session: Session,
    draft: InquiryDraft,
    reference: str,
    link: str,
) -> None:
    """Reference and tracking link to the verified email, and by SMS to a verified mobile.

    A failed send never undoes the submission; it is audited (retries arrive in step 20).
    """
    context = {
        **message_context(draft, runtime.master),
        "reference": reference,
        "tracking_url": link,
    }
    targets: list[tuple[str, str]] = []
    email = draft.fields[FieldKey.EMAIL].value
    if email and draft.email_verified:
        targets.append(("submission_email", str(email)))
    mobile = draft.fields[FieldKey.MOBILE].value
    if mobile and draft.mobile_verified:
        targets.append(("submission_sms", str(mobile)))
    for template, to in targets:
        channel = "sms" if template.endswith("sms") else "email"
        try:
            # The gateway keeps `inquiry_id` for itself; bind the service's own argument.
            send = functools.partial(runtime.services.notifications.send, inquiry_id=session.id)
            message_id = await runtime.services.gateway.call(
                "notifications", "send", send, template, to, context, inquiry_id=session.id
            )
        except GatewayError as err:
            _audit(
                runtime,
                session,
                "notification_sent",
                template=template,
                channel=channel,
                outcome=err.kind,
            )
            continue
        _audit(
            runtime,
            session,
            "notification_sent",
            template=template,
            channel=channel,
            outcome="sent",
            message_id=message_id,
        )


# ---- Intake channels (spec §15) -------------------------------------------------------


async def _send_application_link(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Assisted mode: email the applicant a `complete` link (single use; a resend replaces
    it). The applicant verifies the email by opening it and finishes the inquiry."""
    del payload
    if not session.assisted:
        return ActionResult(note=HumanMessage(content="[ui_event] link_blocked not_assisted"))
    if session.existing_cr_choice == "sign_in":
        return ActionResult(
            note=HumanMessage(content="[ui_event] link_blocked redirected_to_sign_in")
        )
    card = build_send_link_card(session.draft, sent_to=session.link_sent_to)
    if not card.payload["can_send"]:
        missing = ", ".join(card.payload["missing"])
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] link_blocked missing {missing}"),
            events=[_card_event(session, card)],
        )
    email = str(session.draft.fields[FieldKey.EMAIL].value)
    settings = runtime.settings
    token, claims = tokens.issue(
        settings.token_secret,
        "complete",
        session.id,
        ttl_seconds=settings.email_link_ttl_hours * 3600,
    )
    resend = session.complete_nonce is not None
    session.complete_nonce = claims.nonce
    session.link_sent_to = email
    context = {
        **message_context(session.draft, runtime.master),
        "started_by": started_by_label(runtime, session.staff_id),
        "complete_url": f"{settings.public_base_url.rstrip('/')}/inquiry/verify?t={token}",
        "ttl_hours": settings.email_link_ttl_hours,
    }
    send = functools.partial(runtime.services.notifications.send, inquiry_id=session.id)
    try:
        await runtime.services.gateway.call(
            "notifications",
            "send",
            send,
            "complete_application",
            email,
            context,
            inquiry_id=session.id,
        )
    except GatewayError as err:
        return ActionResult(note=HumanMessage(content=f"[ui_event] link_failed {err.kind}"))
    _audit(
        runtime,
        session,
        "application_link_sent",
        by_staff=True,
        by=session.staff_id,
        resend=resend,
    )
    card = build_send_link_card(session.draft, sent_to=email)
    return ActionResult(
        note=HumanMessage(
            content=f"[ui_event] application_link_sent to={card.payload['sent_to_masked']}"
        ),
        events=[_card_event(session, card)],
    )


async def _existing_cr_choice(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """Assisted mode, existing CR: ask them to sign in (no inquiry), or continue for them
    with the tenant record prefilled (intake channels §3.2, §7.1.2 a2)."""
    choice = payload.get("choice")
    cr_number = session.draft.fields[FieldKey.CR_NUMBER].value
    if not session.assisted or session.draft.cr_status != "existing" or not cr_number:
        return ActionResult(note=HumanMessage(content="[ui_event] cr_choice_failed"))
    tenant = runtime.services.tenants.get_by_cr(str(cr_number))
    company = tenant.company_name if tenant else None
    if choice == "sign_in":
        session.existing_cr_choice = "sign_in"
        session.closed = "redirected_to_sign_in"
        _audit(
            runtime,
            session,
            "inquiry_redirected",
            by_staff=True,
            reason="sign_in",
            channel=session.channel,
        )
        card = build_existing_cr_choice_card(str(cr_number), company, chosen="sign_in")
        return ActionResult(
            note=HumanMessage(content="[ui_event] redirected_to_sign_in"),
            events=[_card_event(session, card)],
        )
    if choice != "continue" or tenant is None:
        return ActionResult(note=HumanMessage(content="[ui_event] cr_choice_failed no_record"))
    session.existing_cr_choice = "continue"
    draft, written = prefill_from_tenant(session.draft, tenant, runtime.master)
    draft, documents = attach_documents_on_file(runtime, session.id, draft, tenant)
    session.draft = draft
    session.tenant_id = tenant.id
    _audit(
        runtime,
        session,
        "tenant_prefill",
        by_staff=True,
        tenant_id=tenant.id,
        channel=session.channel,
        keys=written,
        documents=documents,
    )
    card = build_existing_cr_choice_card(str(cr_number), company, chosen="continue")
    brands = "several brands" if len(tenant.brands) > 1 else "one brand"
    return ActionResult(
        note=HumanMessage(
            content=f"[ui_event] tenant_record_loaded {tenant.company_name} ({brands})"
        ),
        events=[_card_event(session, card), _draft_event(draft, runtime, written)],
        changed_keys=written,
    )


async def _proceed_basic_info(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    """The applicant accepts the basic info as shown: every staff, verified or derived
    value on the card is confirmed in one step (intake channels §3.3)."""
    del payload
    new_brand = session.channel == "existing_tenant"  # R4: the brand is asked for in chat
    card = build_basic_info_card(
        session.draft, runtime.master, started_by=None, new_brand=new_brand
    )
    if not card.payload["can_proceed"]:
        missing = ", ".join(card.payload["missing"])
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] basic_info_incomplete {missing}"),
            events=[_card_event(session, card)],
        )
    previous = session.cards.get(BASIC_INFO_CARD_ID, {}).get("payload", {})
    draft, keys = confirm_basic_info(session.draft, new_brand=new_brand)
    session.draft = draft
    _audit(runtime, session, "field_confirmed", keys=keys, via="basic_info_review")
    card = build_basic_info_card(
        draft,
        runtime.master,
        started_by=previous.get("started_by"),
        proceeded=True,
        new_brand=new_brand,
    )
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] basic_info_confirmed {' '.join(keys)}".strip()),
        events=[_card_event(session, card), _draft_event(draft, runtime, keys)],
        changed_keys=keys,
    )
