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
from app.agent.brand_infer import fill_missing_brand_name_en
from app.agent.confirm_policy import keys_blocked_from_confirmation
from app.agent.mall_match import fill_mentioned_malls, filter_mall_ids
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.api.cards import (
    allocate_confirm_card_id,
    build_confirm_fields_card,
    build_document_upload_card,
    build_mall_picker_card,
    build_otp_input_card,
    build_quick_replies_card,
    build_review_card,
    last_confirm_card_id,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.faq import search_faq as faq_search
from app.domain.models import FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_cr_number
from app.services.errors import ReferenceNotFoundError

PROTECTED_WRITE_KEYS = frozenset(
    {
        "terms_accepted",
        "otp_verified",
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
) -> Command[Any]:
    update: dict[str, Any] = {"draft": draft}
    if changed_keys is not None:
        _emit_draft(draft, changed_keys, runtime)
    if cards_shown is not None:
        update["cards_shown"] = cards_shown
    return Command(
        update={
            **update,
            "messages": [
                ToolMessage(content=content, tool_call_id=runtime.tool_call_id or ""),
            ],
        }
    )


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
    result = rt.services.cr.verify(validated)
    draft = state["draft"]
    cards_shown = list(state["cards_shown"])

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
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=updated,
        content="CR verified as new. Company details prefilled for confirmation.",
        changed_keys=written,
        cards_shown=cards_shown,
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
        return json.dumps([u.model_dump() for u in master.unit_types])
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
    updated, brand_en_filled = fill_missing_brand_name_en(updated, user_text)
    if brand_en_filled and FieldKey.BRAND_NAME_EN.value not in written:
        written = [*written, FieldKey.BRAND_NAME_EN.value]
    updated, malls_filled = fill_mentioned_malls(updated, user_text, rt.master)
    if malls_filled and FieldKey.MALLS.value not in written:
        written = [*written, FieldKey.MALLS.value]
    derived_keys = {item.key for item in fields if item.source == "derived"}
    derived_written = [key for key in written if key in derived_keys]

    cards_update = cards_shown
    if derived_written:
        card_id = allocate_confirm_card_id(cards_shown)
        card = build_confirm_fields_card(
            updated,
            rt.master,
            derived_written,
            card_id=card_id,
        )
        if card_id not in cards_shown:
            cards_shown = cards_shown + [card_id]
            cards_update = cards_shown
        _emit_card(card, runtime)

    parts = []
    if written:
        parts.append(f"Updated: {', '.join(written)}.")
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
    not_shown = frozenset(state.get("guard_not_shown") or [])

    confirmable: list[str] = []
    skipped: list[str] = []
    for key_str in keys:
        if key_str in not_shown:
            skipped.append(f"{key_str}: not_shown_in_reply")
            continue
        if key_str in blocked:
            skipped.append(f"{key_str}: user_expressed_doubt")
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
    card_id = last_confirm_card_id(cards_shown)
    if card_id:
        card = build_confirm_fields_card(updated, rt.master, keys, card_id=card_id)
        _emit_card(card, runtime)

    return _tool_result(
        runtime,
        draft=updated,
        content=f"Confirmed: {', '.join(confirmable)}.",
        changed_keys=confirmable,
        cards_shown=cards_shown,
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
async def send_otp(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
    resend: bool = False,
) -> Command[Any]:
    """Send OTP to email and contact number."""
    rt = runtime_from_config(runtime.config)
    draft = state["draft"]
    email = draft.fields[FieldKey.EMAIL].value
    mobile = draft.fields[FieldKey.MOBILE].value
    landline = draft.fields[FieldKey.LANDLINE].value
    phone = mobile or landline
    if not email or not phone:
        return _tool_result(
            runtime,
            draft=draft,
            content="Need email and a contact number before sending OTP.",
        )

    updated = draft.model_copy(deep=True)
    if resend:
        updated.otp_attempts_left = 3
    await rt.services.otp.send(state["session_id"], str(email), str(phone))

    card = build_otp_input_card(updated)
    cards_shown = list(state["cards_shown"])
    if "otp" not in cards_shown:
        cards_shown.append("otp")
    _emit_card(card, runtime)
    return _tool_result(
        runtime,
        draft=updated,
        content="OTP sent." if not resend else "OTP resent.",
        changed_keys=["otp_attempts_left"] if resend else [],
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
    pairs = [(opt, opt) for opt in cleaned]
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
def get_inquiry_status(reference: str, runtime: ToolRuntime) -> str:
    """Look up inquiry status by reference number."""
    rt = runtime_from_config(runtime.config)
    try:
        status = rt.services.status.get(reference)
    except ReferenceNotFoundError:
        return f"No inquiry found for reference {reference}."
    return (
        f"Reference {status.reference} is {status.status}, "
        f"submitted at {status.submitted_at.isoformat()}."
    )


TOOLS = [
    verify_cr,
    skip_cr,
    get_master_data,
    update_draft,
    confirm_fields,
    get_missing_fields,
    show_mall_picker,
    send_otp,
    request_documents,
    show_review,
    suggest_replies,
    search_faq,
    get_inquiry_status,
]
