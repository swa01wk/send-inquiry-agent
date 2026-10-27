"""LangGraph agent tools (spec section 3)."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState, ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.blockers import format_blockers
from app.agent.brand_infer import fill_brands_from_user_message
from app.agent.confirm_policy import key_shown_on_earlier_turn, keys_blocked_from_confirmation
from app.agent.context import message_context
from app.agent.mall_match import fill_mentioned_malls, filter_mall_ids
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.api.cards import (
    VERIFICATION_CARD_ID,
    allocate_confirm_card_id,
    build_confirm_fields_card,
    build_document_upload_card,
    build_mall_picker_card,
    build_quick_replies_card,
    build_review_card,
    confirm_card_id_for_keys,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.faq import search_faq as faq_search
from app.domain.models import FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit, contact_verified
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_cr_number
from app.gateway import GatewayError
from app.policy.config import get_policy
from app.services.errors import ReferenceNotFoundError

PROTECTED_WRITE_KEYS = frozenset(
    {
        "terms_accepted",
        "email_verified",
        "mobile_verified",
        "reference",
        "documents",
        "cr_status",
    }
)


class DraftFieldUpdate(BaseModel):
    key: str
    value: object
    source: Literal["user", "derived"]


def _emit_draft(draft: InquiryDraft, changed_keys: list[str], runtime: ToolRuntime) -> None:
    summary = build_draft_summary(draft, runtime_from_config(runtime.config).master, changed_keys)
    runtime.stream_writer({"type": "draft", "data": summary.model_dump()})


def _emit_card(card: UiCard, runtime: ToolRuntime) -> None:
    runtime.stream_writer({"type": "ui_card", "data": card.model_dump()})


def _tool_result(
    runtime: ToolRuntime,
    *,
    draft: InquiryDraft,
    content: str,
    changed_keys: list[str] | None = None,
    cards_shown: list[str] | None = None,
    confirm_card_keys: dict[str, list[str]] | None = None,
    confirm_card_turns: dict[str, int] | None = None,
) -> Command[Any]:
    update: dict[str, Any] = {"draft": draft}
    if changed_keys is not None:
        _emit_draft(draft, changed_keys, runtime)
    if cards_shown is not None:
        update["cards_shown"] = cards_shown
    if confirm_card_keys is not None:
        update["confirm_card_keys"] = confirm_card_keys
    if confirm_card_turns is not None:
        update["confirm_card_turns"] = confirm_card_turns
    return Command(
        update={
            **update,
            "messages": [
                ToolMessage(content=content, tool_call_id=runtime.tool_call_id or ""),
            ],
        }
    )


def _remember_confirm_card_keys(
    confirm_card_keys: dict[str, list[str]],
    confirm_card_turns: dict[str, int],
    card_id: str,
    keys: list[str],
    turn_index: int,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    updated_keys = dict(confirm_card_keys)
    updated_keys[card_id] = list(keys)
    updated_turns = dict(confirm_card_turns)
    updated_turns[card_id] = turn_index
    return updated_keys, updated_turns


@tool
def verify_cr(
    cr_number: str,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Validate a CR number and look up whether the company already has an account."""
    validated = validate_cr_number(cr_number)
    if isinstance(validated, v.ValidationError):
        return _tool_result(
            runtime,
            draft=state["draft"],
            content=f"Invalid CR: {validated.message}",
        )

    rt = runtime_from_config(runtime.config)
    try:
        result = rt.services.gateway.call_sync(
            "cr", "verify", rt.services.cr.verify, validated, inquiry_id=state["session_id"]
        )
    except GatewayError as err:
        return _tool_result(
            runtime,
            draft=state["draft"],
            content=(
                f"{err.note}: the CR registry didn't answer, so nothing was saved. "
                "Tell the user kindly, and offer to try again in a moment or to continue "
                "without the CR."
            ),
        )
    draft = state["draft"]
    cards_shown = list(state["cards_shown"])

    if result.exists and get_policy().existing_tenant_policy == "allow_inquiry":
        # Requirements §7.1: existing tenants may raise an inquiry from this page.
        # The tenant record prefill arrives with intake channels (step 21c).
        updated, written, _errors = draft_ops.write_fields(
            draft,
            [(FieldKey.CR_NUMBER.value, validated, Source.USER)],
            master=rt.master,
        )
        updated.cr_status = "new"
        return _tool_result(
            runtime,
            draft=updated,
            content=(
                "CR number belongs to an existing Tenant Central account. Policy allows the "
                "inquiry to continue: collect company name and address as usual."
            ),
            changed_keys=written,
            cards_shown=cards_shown,
        )

    if result.exists:
        updated = draft.model_copy(deep=True)
        updated.cr_status = "existing"
        changed = ["cr_number"]
        updated, written, _errors = draft_ops.write_fields(
            updated,
            [(FieldKey.CR_NUMBER.value, validated, Source.USER)],
            master=rt.master,
        )
        changed.extend(written)
        return _tool_result(
            runtime,
            draft=updated,
            content="CR number belongs to an existing Tenant Central account.",
            changed_keys=changed,
            cards_shown=cards_shown,
        )

    entries: list[tuple[str, object, Source]] = [
        (FieldKey.CR_NUMBER.value, validated, Source.USER),
    ]
    if result.company_name:
        entries.append((FieldKey.COMPANY_NAME.value, result.company_name, Source.VERIFIED))
    if result.company_address:
        entries.append((FieldKey.COMPANY_ADDRESS.value, result.company_address, Source.VERIFIED))

    updated, written, errors = draft_ops.write_fields(draft, entries, master=rt.master)
    updated.cr_status = "new"
    if errors:
        msg = "; ".join(f"{key}: {err.message}" for key, err in errors.items())
        return _tool_result(runtime, draft=updated, content=f"CR verified with errors: {msg}")

    confirmable = {FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value}
    confirm_keys = [k for k in written if k in confirmable]
    card_id = allocate_confirm_card_id(cards_shown)
    card = build_confirm_fields_card(
        updated,
        rt.master,
        confirm_keys,
        card_id=card_id,
        title="From your CR — please confirm",
    )
    if card_id not in cards_shown:
        cards_shown.append(card_id)
    confirm_card_keys, confirm_card_turns = _remember_confirm_card_keys(
        dict(state.get("confirm_card_keys", {})),
        dict(state.get("confirm_card_turns", {})),
        card_id,
        confirm_keys,
        state["turn_index"],
    )
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=updated,
        content="CR verified as new. Company details prefilled for confirmation.",
        changed_keys=written,
        cards_shown=cards_shown,
        confirm_card_keys=confirm_card_keys,
        confirm_card_turns=confirm_card_turns,
    )


@tool
def skip_cr(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Skip CR verification after the user agreed."""
    draft = state["draft"]
    if draft.cr_status != "unknown":
        return _tool_result(
            runtime,
            draft=draft,
            content="CR step already completed; cannot skip again.",
        )
    updated = draft.model_copy(deep=True)
    updated.cr_status = "skipped"
    return _tool_result(
        runtime,
        draft=updated,
        content="CR verification skipped.",
        changed_keys=["cr_status"],
    )


@tool
def get_master_data(
    kind: str,
    runtime: ToolRuntime,
    city: str | None = None,
) -> str:
    """Read-only master data lookup."""
    rt = runtime_from_config(runtime.config)
    master = rt.master
    if kind not in {
        "unit_types",
        "sales_categories",
        "cities",
        "malls",
        "lease_periods",
        "rent_periods",
    }:
        return f"Unknown kind: {kind}."
    if kind == "malls":
        malls = master.malls_in_city(city) if city else master.malls
        return json.dumps([m.model_dump() for m in malls])
    if kind == "unit_types":
        lines = get_policy().product_lines
        return json.dumps([u.model_dump() for u in master.unit_types if u.id in lines])
    items = master._items_for_kind(kind)  # noqa: SLF001
    return json.dumps([i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in items])


@tool
def update_draft(
    fields: list[DraftFieldUpdate],
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Write draft fields from user or derived sources."""
    rt = runtime_from_config(runtime.config)
    draft = state["draft"]
    cards_shown = list(state["cards_shown"])
    entries: list[tuple[str, object, Source]] = []
    rejected: list[str] = []

    user_text = _last_user_text(state)
    for item in fields:
        if item.key in PROTECTED_WRITE_KEYS:
            rejected.append(f"{item.key}: protected")
            continue
        if item.source not in ("user", "derived"):
            rejected.append(f"{item.key}: invalid source")
            continue
        if item.key == FieldKey.MALLS.value:
            raw_ids = item.value if isinstance(item.value, list) else []
            existing_raw = draft.fields[FieldKey.MALLS].value
            existing_ids = list(existing_raw) if isinstance(existing_raw, list) else []
            accepted, mall_rejected = filter_mall_ids(
                [str(m) for m in raw_ids],
                [str(m) for m in existing_ids],
                user_text,
                rt.master,
            )
            if mall_rejected:
                rejected.append(
                    f"{item.key}: mall_not_mentioned ({', '.join(mall_rejected)}); "
                    "use show_mall_picker for the city",
                )
            max_malls = get_policy().max_malls_per_inquiry
            if len(accepted) > max_malls:
                code = "one_mall_per_inquiry" if max_malls == 1 else "too_many_malls"
                rejected.append(
                    f"{item.key}: {code} ({', '.join(accepted)}); "
                    "ask which mall to start with and say they can raise another "
                    "inquiry for the others",
                )
                continue
            if not accepted:
                continue
            entries.append((item.key, accepted, Source(item.source)))
            continue
        entries.append((item.key, item.value, Source(item.source)))

    if not entries and rejected:
        updated, malls_filled = fill_mentioned_malls(draft, user_text, rt.master)
        if malls_filled:
            return _tool_result(
                runtime,
                draft=updated,
                content="Updated: malls. Rejected: " + "; ".join(rejected),
                changed_keys=[FieldKey.MALLS.value],
            )
        msg = "No fields written. " + "; ".join(rejected)
        return _tool_result(runtime, draft=draft, content=msg)

    updated, written, errors = draft_ops.write_fields(draft, entries, master=rt.master)
    updated, brands_filled = fill_brands_from_user_message(updated, user_text)
    for key in brands_filled:
        if key not in written:
            written = [*written, key]
    updated, malls_filled = fill_mentioned_malls(updated, user_text, rt.master)
    if malls_filled and FieldKey.MALLS.value not in written:
        written = [*written, FieldKey.MALLS.value]
    derived_keys = {item.key for item in fields if item.source == "derived"}
    derived_written = [key for key in written if key in derived_keys]
    requested_keys = {item.key for item in fields}
    unchanged = sorted(requested_keys - set(written) - set(errors) - set(rejected))

    cards_update = cards_shown
    confirm_card_keys = dict(state.get("confirm_card_keys", {}))
    confirm_card_turns = dict(state.get("confirm_card_turns", {}))
    user_written = [key for key in written if key not in derived_keys]
    card_refresh_keys = list(
        dict.fromkeys(
            [
                *derived_written,
                *[
                    key
                    for key in user_written
                    if confirm_card_id_for_keys(cards_shown, confirm_card_keys, [key])
                ],
            ],
        ),
    )
    if card_refresh_keys:
        existing_id = confirm_card_id_for_keys(cards_shown, confirm_card_keys, card_refresh_keys)
        card_id = existing_id or allocate_confirm_card_id(cards_shown)
        if existing_id:
            card_keys = list(
                dict.fromkeys([*confirm_card_keys.get(existing_id, []), *card_refresh_keys]),
            )
        else:
            card_keys = card_refresh_keys
        card = build_confirm_fields_card(
            updated,
            rt.master,
            card_keys,
            card_id=card_id,
        )
        if card_id not in cards_shown:
            cards_shown = cards_shown + [card_id]
            cards_update = cards_shown
        confirm_card_keys, confirm_card_turns = _remember_confirm_card_keys(
            confirm_card_keys,
            confirm_card_turns,
            card_id,
            card_keys,
            state["turn_index"],
        )
        _emit_card(card, runtime)

    parts = []
    if written:
        parts.append(f"Updated: {', '.join(written)}.")
    if unchanged:
        parts.append(f"Unchanged: {', '.join(unchanged)}.")
    if errors:
        parts.append("Errors: " + "; ".join(f"{k}: {v.message}" for k, v in errors.items()))
    if rejected:
        parts.append("Rejected: " + "; ".join(rejected))
    return _tool_result(
        runtime,
        draft=updated,
        content=" ".join(parts) or "Nothing changed.",
        changed_keys=written,
        cards_shown=cards_update,
        confirm_card_keys=confirm_card_keys,
        confirm_card_turns=confirm_card_turns,
    )


def _last_user_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if not isinstance(message, HumanMessage):
            continue
        content = message.content
        text = content if isinstance(content, str) else str(content)
        if text.startswith("[ui_event]"):
            continue
        return text
    return ""


@tool
def confirm_fields(
    keys: list[str],
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Confirm derived or verified field values after the user agreed."""
    rt = runtime_from_config(runtime.config)
    draft = state["draft"]
    cards_shown = list(state["cards_shown"])
    blocked = keys_blocked_from_confirmation(_last_user_text(state))
    confirm_card_keys = dict(state.get("confirm_card_keys", {}))
    confirm_card_turns = dict(state.get("confirm_card_turns", {}))
    turn_index = state.get("turn_index", 0)

    confirmable: list[str] = []
    skipped: list[str] = []
    for key_str in keys:
        if key_str in blocked:
            skipped.append(f"{key_str}: user_expressed_doubt")
            continue
        if not key_shown_on_earlier_turn(
            key_str, confirm_card_keys, confirm_card_turns, turn_index
        ):
            skipped.append(f"{key_str}: not_shown")
            continue
        try:
            key = FieldKey(key_str)
        except ValueError:
            skipped.append(key_str)
            continue
        field = draft.fields[key]
        if field.value is None:
            skipped.append(key_str)
            continue
        if field.source not in (Source.DERIVED, Source.VERIFIED):
            skipped.append(key_str)
            continue
        if field.confirmed:
            skipped.append(key_str)
            continue
        confirmable.append(key_str)

    if not confirmable:
        return _tool_result(
            runtime,
            draft=draft,
            content="No fields confirmed."
            + (f" Skipped: {', '.join(skipped)}." if skipped else ""),
        )

    updated = draft_ops.confirm(draft, confirmable)
    card_id = confirm_card_id_for_keys(cards_shown, confirm_card_keys, confirmable)
    if card_id:
        listed = confirm_card_keys.get(card_id, confirmable)
        card = build_confirm_fields_card(updated, rt.master, listed, card_id=card_id)
        _emit_card(card, runtime)

    return _tool_result(
        runtime,
        draft=updated,
        content=f"Confirmed: {', '.join(confirmable)}.",
        changed_keys=confirmable,
        cards_shown=cards_shown,
        confirm_card_keys=confirm_card_keys,
        confirm_card_turns=confirm_card_turns,
    )


@tool
def get_missing_fields(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> str:
    """List submit blockers in plain language."""
    del runtime
    blockers = can_submit(state["draft"])
    return format_blockers(blockers)


@tool
def show_mall_picker(
    city: str,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show mall picker card for a city."""
    rt = runtime_from_config(runtime.config)
    if city not in rt.master.ids_for_kind("cities"):
        return _tool_result(runtime, draft=state["draft"], content=f"Unknown city: {city}.")
    card = build_mall_picker_card(state["draft"], rt.master, city)
    cards_shown = list(state["cards_shown"])
    if "malls" not in cards_shown:
        cards_shown.append("malls")
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=state["draft"],
        content=f"Mall picker shown for {city}.",
        cards_shown=cards_shown,
    )


@tool
async def send_verification(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
    resend: bool = False,
) -> Command[Any]:
    """Verify the contact: email a one-time link, and text a code if a mobile was given.

    A landline-only applicant is verified by email alone. Set resend=True only when
    the user asks for a new link or code.
    """
    rt = runtime_from_config(runtime.config)
    draft = state["draft"]
    session_id = state["session_id"]
    email = draft.fields[FieldKey.EMAIL].value
    mobile = draft.fields[FieldKey.MOBILE].value
    landline = draft.fields[FieldKey.LANDLINE].value
    if not email or not (mobile or landline):
        return _tool_result(
            runtime,
            draft=draft,
            content="Need email and a contact number before verification.",
        )

    services = rt.services
    audit = services.audit
    context = message_context(draft, rt.master)
    updated = draft.model_copy(deep=True)
    sent: list[str] = []
    throttled: list[int] = []
    failures: list[str] = []

    email_text = str(email)
    if not updated.email_verified and (resend or updated.email_link_sent_to != email_text):
        is_resend = updated.email_link_sent_to == email_text
        wait = services.resend.wait_seconds(session_id, "email") if is_resend else 0
        if wait:
            throttled.append(wait)
            audit.record(
                session_id,
                "verification_sent",
                actor="agent",
                payload={"channel": "email", "result": "throttled"},
            )
        else:
            try:
                await services.gateway.call(
                    "email",
                    "send_link",
                    services.email_verification.send_link,
                    session_id,
                    email_text,
                    context,
                    inquiry_id=session_id,
                )
            except GatewayError as err:
                failures.append(err.note)
                audit.record(
                    session_id,
                    "verification_sent",
                    actor="agent",
                    payload={"channel": "email", "result": err.kind},
                )
            else:
                services.resend.record(session_id, "email")
                updated.email_link_sent_to = email_text
                sent.append("email verification link")
                audit.record(
                    session_id,
                    "verification_sent",
                    actor="agent",
                    payload={"channel": "email", "result": "sent"},
                )

    mobile_text = str(mobile) if mobile else None
    if (
        mobile_text
        and not updated.mobile_verified
        and (resend or updated.otp_sent_to != mobile_text)
    ):
        is_resend = updated.otp_sent_to == mobile_text
        wait = services.resend.wait_seconds(session_id, "sms") if is_resend else 0
        if wait:
            throttled.append(wait)
            audit.record(
                session_id,
                "verification_sent",
                actor="agent",
                payload={"channel": "sms", "result": "throttled"},
            )
        else:
            try:
                await services.gateway.call(
                    "otp",
                    "send",
                    services.otp.send,
                    session_id,
                    mobile_text,
                    context,
                    inquiry_id=session_id,
                )
            except GatewayError as err:
                failures.append(err.note)
                audit.record(
                    session_id,
                    "verification_sent",
                    actor="agent",
                    payload={"channel": "sms", "result": err.kind},
                )
            else:
                services.resend.record(session_id, "sms")
                updated.otp_sent_to = mobile_text
                updated.otp_attempts_left = 3
                sent.append("mobile code")
                audit.record(
                    session_id,
                    "verification_sent",
                    actor="agent",
                    payload={"channel": "sms", "result": "sent"},
                )

    card = rt.verification_card(updated, session_id)
    cards_shown = list(state["cards_shown"])
    if VERIFICATION_CARD_ID not in cards_shown:
        cards_shown.append(VERIFICATION_CARD_ID)
    _emit_card(card, runtime)

    parts: list[str] = []
    if contact_verified(updated):
        parts.append("Contact already verified.")
    elif sent:
        parts.append(f"Sent: {' and '.join(sent)}.")
        if not mobile_text:
            parts.append("No mobile given, so the email link alone verifies this applicant.")
    elif not throttled and not failures:
        parts.append("Verification already sent; waiting for the user to complete it in the card.")
    if throttled:
        parts.append(
            f"resend_throttled {max(throttled)}: a new link or code can be sent in "
            f"{max(throttled)} seconds; the card shows when."
        )
    for note in failures:
        parts.append(
            f"{note}: that message couldn't be sent. Tell the user kindly and offer to try "
            "again in a moment; nothing else is lost."
        )
    return _tool_result(
        runtime,
        draft=updated,
        content=" ".join(parts),
        changed_keys=["otp_attempts_left"] if "mobile code" in sent else None,
        cards_shown=cards_shown,
    )


@tool
def request_documents(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show the document upload checklist card."""
    rt = runtime_from_config(runtime.config)
    card = build_document_upload_card(
        state["draft"],
        rt.master,
        max_mb=rt.settings.max_upload_mb,
    )
    cards_shown = list(state["cards_shown"])
    if "documents" not in cards_shown:
        cards_shown.append("documents")
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=state["draft"],
        content="Document checklist shown.",
        cards_shown=cards_shown,
    )


@tool
def show_review(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show review card when only terms acceptance remains."""
    rt = runtime_from_config(runtime.config)
    blockers = can_submit(state["draft"])
    from app.domain.models import Blocker

    only_terms = blockers == [Blocker.terms_not_accepted()]
    if not only_terms:
        return _tool_result(
            runtime,
            draft=state["draft"],
            content="Cannot show review yet: " + format_blockers(blockers),
        )
    card = build_review_card(state["draft"], rt.master)
    cards_shown = list(state["cards_shown"])
    if "review" not in cards_shown:
        cards_shown.append("review")
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=state["draft"],
        content="Review card shown.",
        cards_shown=cards_shown,
    )


@tool
def suggest_replies(
    options: list[str],
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Suggest quick-reply chips for this turn."""
    cleaned = [opt.strip() for opt in options if opt.strip()]
    if not 1 <= len(cleaned) <= 3:
        return _tool_result(
            runtime,
            draft=state["draft"],
            content="Provide 1 to 3 reply options.",
        )
    too_long = [opt for opt in cleaned if len(opt) > 60]
    if too_long:
        return _tool_result(
            runtime,
            draft=state["draft"],
            content="Each reply option must be 60 characters or less.",
        )
    pairs: list[tuple[str, str, str | None, str | None]] = [
        (opt, opt, None, None) for opt in cleaned
    ]
    card = build_quick_replies_card(pairs)
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=state["draft"],
        content="Quick replies suggested.",
    )


@tool
def search_faq(query: str, runtime: ToolRuntime) -> str:
    """Search FAQ entries by keyword."""
    del runtime
    matches = faq_search(query, k=2)
    if not matches:
        return "No FAQ matches."
    parts = [f"Q: {m.question}\nA: {m.answer}" for m in matches]
    return "\n\n".join(parts)


@tool
def get_inquiry_status(
    reference: str,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> str:
    """Look up inquiry status by reference number."""
    rt = runtime_from_config(runtime.config)
    own = state["draft"].reference
    if reference.strip().upper() != (own or "").upper():
        # A reference alone must not expose an applicant's case (L3 §3.4).
        return (
            "For privacy, only this conversation's own inquiry can be looked up here. "
            "Other inquiries are tracked from the private link in the submission email."
        )
    try:
        status = rt.services.gateway.call_sync(
            "status", "get", rt.services.status.get, own, inquiry_id=state["session_id"]
        )
    except ReferenceNotFoundError:
        return f"No inquiry found for reference {reference}."
    except GatewayError as err:
        return f"{err.note}: the status service didn't answer; offer to try again later."
    return (
        f"Reference {status.reference} is {status.status}, in {status.current_stage} with "
        f"the {status.owner_role}, submitted at {status.submitted_at.isoformat()}."
    )


TOOLS = [
    verify_cr,
    skip_cr,
    get_master_data,
    update_draft,
    confirm_fields,
    get_missing_fields,
    show_mall_picker,
    send_verification,
    request_documents,
    show_review,
    suggest_replies,
    search_faq,
    get_inquiry_status,
]
