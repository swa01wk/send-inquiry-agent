"""UI actions handled before the agent graph runs (spec section 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage

from app.agent.events import SseEvent
from app.agent.runtime import AgentRuntime
from app.api.cards import (
    build_confirm_fields_card,
    build_otp_input_card,
    build_review_card,
    build_success_card,
    last_confirm_card_id,
    remember_confirm_card_keys,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.models import FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_malls
from app.sessions import Session


@dataclass
class ActionResult:
    note: HumanMessage
    events: list[SseEvent] = field(default_factory=list)
    changed_keys: list[str] = field(default_factory=list)


def _draft_event(draft: InquiryDraft, runtime: AgentRuntime, changed_keys: list[str]) -> SseEvent:
    summary = build_draft_summary(draft, runtime.master, changed_keys)
    return SseEvent(event="draft", data=summary.model_dump())


def _card_event(session: Session, card: UiCard) -> SseEvent:
    remember_confirm_card_keys(session, card)
    return SseEvent(event="ui_card", data=card.model_dump())


async def handle_ui_action(
    action: str,
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    handlers = {
        "select_malls": _select_malls,
        "submit_otp": _submit_otp,
        "resend_otp": _resend_otp,
        "edit_field": _edit_field,
        "confirm_card": _confirm_card,
        "accept_and_submit": _accept_and_submit,
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
        return ActionResult(note=HumanMessage(content="[ui_event] malls_invalid"))
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


async def _submit_otp(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    code = str(payload.get("code", ""))
    draft = session.draft.model_copy(deep=True)
    verified = await runtime.services.otp.verify(session.id, code)
    events: list[SseEvent] = []

    if verified:
        draft.otp_verified = True
        session.draft = draft
        card = build_otp_input_card(draft)
        events.append(_card_event(session, card))
        events.append(_draft_event(draft, runtime, ["otp_verified"]))
        return ActionResult(
            note=HumanMessage(content="[ui_event] otp_verified"),
            events=events,
            changed_keys=["otp_verified"],
        )

    draft.otp_attempts_left = max(0, draft.otp_attempts_left - 1)
    if draft.otp_attempts_left <= 0:
        email = draft.fields[FieldKey.EMAIL].value
        phone = draft.fields[FieldKey.MOBILE].value or draft.fields[FieldKey.LANDLINE].value
        if email and phone:
            await runtime.services.otp.send(session.id, str(email), str(phone))
        draft.otp_attempts_left = 3
        session.draft = draft
        card = build_otp_input_card(draft)
        events.extend(
            [_card_event(session, card), _draft_event(draft, runtime, ["otp_attempts_left"])],
        )
        return ActionResult(
            note=HumanMessage(content="[ui_event] otp_resent"),
            events=events,
            changed_keys=["otp_attempts_left"],
        )

    session.draft = draft
    card = build_otp_input_card(draft)
    events.extend([_card_event(session, card), _draft_event(draft, runtime, ["otp_attempts_left"])])
    return ActionResult(
        note=HumanMessage(
            content=f"[ui_event] otp_failed attempts_left={draft.otp_attempts_left}",
        ),
        events=events,
        changed_keys=["otp_attempts_left"],
    )


async def _resend_otp(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    del payload
    draft = session.draft.model_copy(deep=True)
    email = draft.fields[FieldKey.EMAIL].value
    phone = draft.fields[FieldKey.MOBILE].value or draft.fields[FieldKey.LANDLINE].value
    if not email or not phone:
        return ActionResult(
            note=HumanMessage(content="[ui_event] otp_send_blocked missing_contact"),
        )
    await runtime.services.otp.send(session.id, str(email), str(phone))
    draft.otp_attempts_left = 3
    session.draft = draft
    card = build_otp_input_card(draft)
    return ActionResult(
        note=HumanMessage(content="[ui_event] otp_resent"),
        events=[_card_event(session, card), _draft_event(draft, runtime, ["otp_attempts_left"])],
        changed_keys=["otp_attempts_left"],
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
    draft, written, errors = draft_ops.write_fields(
        session.draft,
        [(key, value, Source.USER)],
        master=runtime.master,
    )
    if errors or not written:
        return ActionResult(note=HumanMessage(content=f"[ui_event] field_edit_failed {key}"))
    session.draft = draft
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] field_edited {key}"),
        events=[_draft_event(draft, runtime, written)],
        changed_keys=written,
    )


async def _confirm_card(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    card_id = payload.get("card_id")
    if not isinstance(card_id, str):
        return ActionResult(note=HumanMessage(content="[ui_event] confirm_failed"))
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
        if field.source in (Source.DERIVED, Source.VERIFIED) and not field.confirmed:
            keys.append(key_str)
    if not keys:
        return ActionResult(note=HumanMessage(content="[ui_event] confirm_failed"))
    draft = draft_ops.confirm(session.draft, keys)
    session.draft = draft
    events: list[SseEvent] = [_draft_event(draft, runtime, keys)]
    confirm_id = last_confirm_card_id(list(session.cards_shown)) or card_id
    card = build_confirm_fields_card(draft, runtime.master, keys, card_id=confirm_id)
    events.append(_card_event(session, card))
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] fields_confirmed {' '.join(keys)}"),
        events=events,
        changed_keys=keys,
    )


async def _accept_and_submit(
    payload: dict[str, Any],
    session: Session,
    runtime: AgentRuntime,
) -> ActionResult:
    if payload.get("terms_accepted") is not True:
        return ActionResult(
            note=HumanMessage(content="[ui_event] submit_blocked terms_not_accepted"),
        )
    draft = session.draft.model_copy(deep=True)
    draft.terms_accepted = True
    blockers = can_submit(draft)
    if blockers:
        session.draft = draft
        card = build_review_card(draft, runtime.master)
        if "review" not in session.cards_shown:
            session.cards_shown.add("review")
        tokens = " ".join(b.token for b in blockers)
        return ActionResult(
            note=HumanMessage(content=f"[ui_event] submit_blocked {tokens}"),
            events=[_card_event(session, card), _draft_event(draft, runtime, ["terms_accepted"])],
            changed_keys=["terms_accepted"],
        )

    reference = runtime.services.submit.submit(draft, runtime.master)
    draft.reference = reference
    session.draft = draft
    success = build_success_card(reference)
    session.cards_shown.add("success")
    return ActionResult(
        note=HumanMessage(content=f"[ui_event] submitted reference={reference}"),
        events=[
            _card_event(session, success),
            _draft_event(draft, runtime, ["reference", "terms_accepted"]),
        ],
        changed_keys=["reference", "terms_accepted"],
    )
