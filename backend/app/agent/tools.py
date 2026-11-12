"""LangGraph agent tools (spec section 3)."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState, ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agent.blockers import format_blockers
from app.agent.brand_infer import fill_brands_from_user_message
from app.agent.confirm_policy import (
    expresses_general_doubt,
    key_shown_on_earlier_turn,
    keys_blocked_from_confirmation,
)
from app.agent.cr_check import apply_cr_result
from app.agent.cr_question import apply_cr_answer, cr_question_active
from app.agent.mall_match import (
    fill_mentioned_malls,
    filter_mall_ids,
    mentioned_seed_mall_ids,
)
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.agent.verification import send_contact_verification
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
from app.api.channel_cards import (
    BASIC_INFO_CARD_ID,
    CR_QUESTION_CARD_ID,
    EXISTING_CR_CARD_ID,
    SEND_LINK_CARD_ID,
    SIGN_IN_CARD_ID,
    build_basic_info_card,
    build_company_registration_card,
    build_cr_question_card,
    build_existing_cr_choice_card,
    build_send_link_card,
    build_sign_in_prompt_card,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.faq import search_faq as faq_search
from app.domain.models import EVIDENCE_MAX_CHARS, NEEDS_CONFIRMATION, FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit, contact_verified
from app.domain.summary import build_draft_summary
from app.domain.validation import validate_cr_number
from app.gateway import GatewayError
from app.policy.config import get_policy
from app.services.errors import ReferenceNotFoundError
from app.workflow.flow import FlowNode, record_flow_step

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


_WRITABLE_KEYS = ", ".join(
    [k.value for k in FieldKey if k is not FieldKey.MOBILE and k is not FieldKey.LANDLINE]
    + ["contact_number", "landline (only when they say it's a landline)"]
)


class DraftFieldUpdate(BaseModel):
    key: str = Field(
        description=(
            f"One of: {_WRITABLE_KEYS}. Space: `area` (sqm, one value or a range like "
            "'25-35') or area_min/area_max; `rent` (SAR, e.g. '250000 per year' or a range) "
            "or rent_min/rent_max; rent_period `yearly`/`monthly`; lease_period `1y`, `2y`, "
            "`3y` or `5y`. Any other key is rejected."
        ),
    )
    value: object
    source: Literal["user", "derived"]
    evidence: str | None = Field(
        default=None,
        description=(
            "Only for source=derived: the user's own words the value was derived from, "
            f"quoted exactly (at most {EVIDENCE_MAX_CHARS} characters), e.g. "
            "'specialty coffee kiosk'. The user sees it on the confirm card."
        ),
    )


_QUOTE_STRIP = " \t\n\"'“”‘’«».,;:!?؟،"


def _normalise_quote(text: str) -> str:
    return " ".join(v.normalise_digits(text).casefold().split()).strip(_QUOTE_STRIP)


def _user_words(state: AgentState) -> str:
    """Everything the user typed in this conversation (UI notes excluded), normalised."""
    parts: list[str] = []
    for message in state["messages"]:
        if not isinstance(message, HumanMessage):
            continue
        content = message.content
        text = content if isinstance(content, str) else str(content)
        if not text.startswith("[ui_event]"):
            parts.append(text)
    return _normalise_quote(" \n ".join(parts))


def _category_from_brand_only(
    item: DraftFieldUpdate,
    fields: list[DraftFieldUpdate],
    draft: InquiryDraft,
    user_text: str = "",
) -> bool:
    """A derived Sales Category based on nothing but the brand name (V12).

    The basis is the model's evidence or, when it gave none, the user's last message. It
    counts as brand-only when nothing is left once the brand names are taken out.
    """
    basis = " ".join((item.evidence or user_text or "").split()).strip(_QUOTE_STRIP).lower()
    if not basis:
        return True
    brands = {
        str(f.value).strip().lower()
        for f in fields
        if f.key in (FieldKey.BRAND_NAME_EN.value, FieldKey.BRAND_NAME_AR.value) and f.value
    }
    for key in (FieldKey.BRAND_NAME_EN, FieldKey.BRAND_NAME_AR):
        value = draft.fields[key].value
        if value:
            brands.add(str(value).strip().lower())
    rest = basis
    for brand in sorted(brands, key=len, reverse=True):
        rest = rest.replace(brand, " ")
    return not re.search(r"\w{3,}", rest)


def _evidence_for(
    fields: list[DraftFieldUpdate], state: AgentState
) -> tuple[dict[str, str], list[str]]:
    """Evidence for derived entries that really quotes the user (L3 §3.9).

    A quote the user never wrote is dropped (the value is still saved), so the confirm
    card never shows words put in the user's mouth.
    """
    kept: dict[str, str] = {}
    dropped: list[str] = []
    said = _user_words(state)
    for item in fields:
        if item.source != "derived" or not item.evidence or not item.evidence.strip():
            continue
        quote = " ".join(item.evidence.split()).strip(_QUOTE_STRIP)
        if len(quote) > EVIDENCE_MAX_CHARS:
            quote = quote[:EVIDENCE_MAX_CHARS].rsplit(" ", 1)[0]
        if quote and _normalise_quote(quote) in said:
            kept[item.key] = quote
        else:
            dropped.append(item.key)
    return kept, dropped


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


def _write_source(source: str, state: AgentState) -> Source:
    """In assisted mode the executive types what the caller said: `user` becomes `staff`."""
    if source == "user" and state.get("assisted"):
        return Source.STAFF
    return Source(source)


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
    if state["draft"].intake_flow == "v2" and not state.get("assisted"):
        # Flow v2 (§3.2, ADR-V4): the CR is checked on the Company Registration card (or
        # when typed in the chat), never by the model.
        return _tool_result(
            runtime,
            draft=state["draft"],
            content=(
                "Not here: the CR is checked on the Company Registration card (Verify), or "
                "they can Skip. Nothing was checked or saved; never repeat a number."
            ),
        )
    if cr_question_active(
        assisted=bool(state.get("assisted")),
        channel=state.get("channel"),
        test_scenario=state.get("test_scenario"),
    ):
        # Demo feedback §3.1: the public page never looks a CR up or repeats one.
        return _tool_result(
            runtime,
            draft=state["draft"],
            content=(
                "CR lookups are off on this page: nothing was checked or saved. Ask whether "
                "the company has a CR (the card), never for the number, and don't repeat it."
            ),
        )
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
    cards_shown = list(state["cards_shown"])
    tenant = rt.services.tenants.get_by_cr(validated) if result.exists else None
    outcome = apply_cr_result(state["draft"], validated, result, rt.master, tenant=tenant)
    updated = outcome.draft

    if outcome.kind == "existing_allowed":
        if tenant is None:
            return _tool_result(
                runtime,
                draft=updated,
                content=(
                    "CR number belongs to an existing Tenant Central account. Policy allows "
                    "the inquiry to continue: collect company name and address as usual."
                ),
                changed_keys=outcome.changed,
                cards_shown=cards_shown,
            )
        # Intake channels §3.6: prefilled from the tenant record, reviewed in one card.
        card = build_basic_info_card(updated, rt.master, started_by="your Tenant Central record")
        _emit_card(card, runtime)
        if BASIC_INFO_CARD_ID not in cards_shown:
            cards_shown.append(BASIC_INFO_CARD_ID)
        brand_note = (
            " The tenant has several brands: ask which one this inquiry is for (or a new one)."
            if len(tenant.brands) > 1
            else ""
        )
        return _tool_result(
            runtime,
            draft=updated,
            content=(
                f"Existing tenant {tenant.company_name}: details prefilled from their Tenant "
                "Central record and shown on a review card. Ask them to check it and press "
                "Proceed (or edit a field); then continue with what's still missing." + brand_note
            ),
            changed_keys=outcome.changed,
            cards_shown=cards_shown,
        )

    if outcome.kind == "existing":
        if state.get("assisted"):
            # Intake channels §3.2: the executive chooses (sign in, or continue for them).
            card = build_existing_cr_choice_card(validated, tenant.company_name if tenant else None)
            _emit_card(card, runtime)
            if EXISTING_CR_CARD_ID not in cards_shown:
                cards_shown.append(EXISTING_CR_CARD_ID)
            content = (
                "This CR already has a Tenant Central account"
                + (f" ({tenant.company_name})" if tenant else "")
                + ". The executive chooses on the card: ask the caller to sign in to Tenant "
                "Central, or continue the inquiry for them with the tenant record prefilled."
            )
        else:
            # Intake channels §3.6 (sign_in): a button to Tenant Central; no inquiry here.
            card = build_sign_in_prompt_card(rt.settings.public_base_url)
            _emit_card(card, runtime)
            if SIGN_IN_CARD_ID not in cards_shown:
                cards_shown.append(SIGN_IN_CARD_ID)
            rt.services.audit.record(
                state["session_id"],
                "inquiry_redirected",
                actor="system",
                payload={"reason": "sign_in", "channel": state.get("channel", "self_service")},
            )
            content = (
                "CR number belongs to an existing Tenant Central account. A Sign in to "
                "Tenant Central button is on the card; explain kindly and stop collecting."
            )
        return _tool_result(
            runtime,
            draft=updated,
            content=content,
            changed_keys=outcome.changed,
            cards_shown=cards_shown,
        )

    written = outcome.changed
    if outcome.errors:
        msg = "; ".join(f"{key}: {err.message}" for key, err in outcome.errors.items())
        return _tool_result(runtime, draft=updated, content=f"CR verified with errors: {msg}")

    confirm_keys = outcome.confirm_keys
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
    confirmed: bool = False,
) -> Command[Any]:
    """Skip CR verification after the user agreed. On the Company Registration card the
    first call shows "Are you sure you want to proceed without CR ID?"; call again with
    confirmed=true only after the user said yes to that question."""
    draft = state["draft"]
    if draft.cr_status != "unknown":
        return _tool_result(
            runtime,
            draft=draft,
            content="CR step already completed; cannot skip again.",
        )
    if draft.intake_flow == "v2" and not state.get("assisted"):
        return _v2_skip_cr(state, runtime, confirmed=confirmed)
    updated = draft.model_copy(deep=True)
    updated.cr_status = "skipped"
    return _tool_result(
        runtime,
        draft=updated,
        content="CR verification skipped.",
        changed_keys=["cr_status"],
    )


def _v2_skip_cr(state: AgentState, runtime: ToolRuntime, *, confirmed: bool) -> Command[Any]:
    """Flow v2 (§3.2): Skip needs the confirmation, as on the card."""
    draft = state["draft"]
    if not confirmed:
        _emit_card(build_company_registration_card(state="confirm_skip"), runtime)
        return _tool_result(
            runtime,
            draft=draft,
            content=(
                'The card now asks "Are you sure you want to proceed without CR ID?". Call '
                "skip_cr(confirmed=true) only after they say yes to that question."
            ),
        )
    rt = runtime_from_config(runtime.config)
    updated = draft.model_copy(deep=True)
    updated.cr_status = "skipped"
    session_id = state["session_id"]
    record_flow_step(rt, inquiry_id=session_id, node=FlowNode.CHK_TP, actor="user")
    record_flow_step(rt, inquiry_id=session_id, node=FlowNode.EXIST, outcome="skipped")
    _emit_card(build_company_registration_card(state="skipped"), runtime)
    return _tool_result(
        runtime,
        draft=updated,
        content="Company Registration skipped.",
        changed_keys=["cr_status"],
    )


@tool
def record_cr_answer(
    has_cr: bool,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Record the user's answer to "Do you have a CR?" when they answer in words (the card's
    buttons do the same). has_cr=true: they have one, so they sign in instead; false: no CR.
    Never ask for, pass or repeat the CR number."""
    draft = state["draft"]
    if not cr_question_active(
        assisted=bool(state.get("assisted")),
        channel=state.get("channel"),
        test_scenario=state.get("test_scenario"),
    ):
        return _tool_result(runtime, draft=draft, content="Not used in this chat.")
    answered = apply_cr_answer(draft, has_cr)
    if answered is None:
        return _tool_result(runtime, draft=draft, content="The CR question is already answered.")
    cards_shown = list(state["cards_shown"])
    _emit_card(build_cr_question_card(answered="yes" if has_cr else "no"), runtime)
    if CR_QUESTION_CARD_ID not in cards_shown:
        cards_shown.append(CR_QUESTION_CARD_ID)
    if has_cr:
        rt = runtime_from_config(runtime.config)
        _emit_card(build_sign_in_prompt_card(rt.settings.public_base_url, reason="has_cr"), runtime)
        if SIGN_IN_CARD_ID not in cards_shown:
            cards_shown.append(SIGN_IN_CARD_ID)
        rt.services.audit.record(
            state["session_id"],
            "inquiry_redirected",
            actor="system",
            payload={"reason": "has_cr", "channel": state.get("channel", "self_service")},
        )
        content = (
            "Recorded: the company has a CR. A Sign in to Tenant Central card is shown. In one "
            "or two warm sentences, say signing in is quickest (their details are on file) "
            "and stop collecting."
        )
    else:
        content = (
            "Recorded: no CR. Carry on: ask for the company name and address together, then "
            "the brand and space."
        )
    return _tool_result(
        runtime,
        draft=answered.draft,
        content=content,
        changed_keys=answered.changed,
        cards_shown=cards_shown,
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
    arabic_brand_en_redirect = False

    user_text = _last_user_text(state)
    keys_in_call = {item.key for item in fields}
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
            named = mentioned_seed_mall_ids(user_text, rt.master)
            if len(named) > max_malls:
                # The user named more malls than one inquiry covers: the agent may not pick
                # for them (policy max_malls_per_inquiry; regression seen in eval "Two malls").
                code = "one_mall_per_inquiry" if max_malls == 1 else "too_many_malls"
                rejected.append(
                    f"{item.key}: {code} (the user named {', '.join(named)}); save no mall, "
                    "ask which one to start with, and say they can raise another inquiry "
                    "for the others",
                )
                continue
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
            entries.append((item.key, accepted, _write_source(item.source, state)))
            continue
        if (
            item.key == FieldKey.SALES_CATEGORY.value
            and draft.intake_flow == "v2"
            and item.source == "derived"
            and _category_from_brand_only(item, fields, draft, user_text)
        ):
            # Flow v2 (V12, FV11): the category comes from what the business sells.
            rejected.append(
                f"{item.key}: category_needs_what_you_sell; ask what they sell, then map it "
                "and show it for confirmation"
            )
            continue
        if item.key == FieldKey.BRAND_NAME_EN.value:
            val = item.value
            if isinstance(val, str) and v.ARABIC_RE.search(val):
                if FieldKey.BRAND_NAME_AR.value not in keys_in_call:
                    # Keep the model's own source: a heuristic redirect never upgrades a
                    # value to `user` (guard rule; a product word like «قهوة» must stay
                    # confirmable).
                    entries.append(
                        (FieldKey.BRAND_NAME_AR.value, val, _write_source(item.source, state)),
                    )
                arabic_brand_en_redirect = True
                continue
        entries.append((item.key, item.value, _write_source(item.source, state)))

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

    evidence, evidence_dropped = _evidence_for(fields, state)
    updated, written, errors = draft_ops.write_fields(
        draft, entries, master=rt.master, evidence=evidence
    )
    updated, brands_filled = fill_brands_from_user_message(updated, user_text)
    for key in brands_filled:
        if key not in written:
            written = [*written, key]
    updated, malls_filled = fill_mentioned_malls(updated, user_text, rt.master)
    if malls_filled and FieldKey.MALLS.value not in written:
        written = [*written, FieldKey.MALLS.value]
    derived_keys = {
        key for item in fields if item.source == "derived" for key in _written_by(item.key)
    }
    derived_written = [key for key in written if key in derived_keys]
    # Pseudo keys report through the fields they write (or their own error).
    requested_keys = {item.key for item in fields if item.key not in _PSEUDO_KEY_TARGETS}
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
        if any(err.code == "unknown_field" for err in errors.values()):
            # Seen in live eval: invented keys such as area_min_sqm or rent_annual_sar.
            parts.append(f"Use only these keys, then call update_draft again: {_WRITABLE_KEYS}.")
    if rejected:
        parts.append("Rejected: " + "; ".join(rejected))
    if evidence_dropped:
        parts.append(
            "Evidence ignored (not the user's exact words): " + ", ".join(evidence_dropped) + "."
        )
    if arabic_brand_en_redirect:
        parts.append(
            "Arabic brand saved as brand_name_ar; now save a Latin spelling as "
            "brand_name_en (source derived).",
        )
    return _tool_result(
        runtime,
        draft=updated,
        content=" ".join(parts) or "Nothing changed.",
        changed_keys=written,
        cards_shown=cards_update,
        confirm_card_keys=confirm_card_keys,
        confirm_card_turns=confirm_card_turns,
    )


# Pseudo keys that write other fields (draft_ops.write_fields): `area` and `rent` are the
# summary rows' names, which the model uses too (eval trace, 2 Nov 2026).
_PSEUDO_KEY_TARGETS: dict[str, tuple[str, ...]] = {
    "area": (FieldKey.AREA_MIN.value, FieldKey.AREA_MAX.value),
    "rent": (FieldKey.RENT_MIN.value, FieldKey.RENT_MAX.value, FieldKey.RENT_PERIOD.value),
}


def _written_by(key: str) -> tuple[str, ...]:
    return _PSEUDO_KEY_TARGETS.get(key, (key,))


def _last_user_text(state: AgentState) -> str:
    for message in reversed(state["messages"]):
        if not isinstance(message, HumanMessage):
            continue
        content = message.content
        text = content if isinstance(content, str) else str(content)
        if text.startswith("[ui_event]"):
            continue
        return v.normalise_digits(text)
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
    user_text = _last_user_text(state)
    blocked = keys_blocked_from_confirmation(user_text)
    if expresses_general_doubt(user_text):
        # "Hmm, not sure" / «مو متأكد» doubts whatever was just asked: confirm nothing.
        blocked = blocked | frozenset(keys)
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
        if field.source not in NEEDS_CONFIRMATION:
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
    # The model often passes the city's name ("Jeddah") rather than its id ("jeddah").
    wanted = city.strip().lower()
    match = next(
        (
            c.id
            for c in rt.master.cities
            if wanted in {c.id.lower(), c.label.lower(), (c.label_ar or "").strip()}
        ),
        None,
    )
    if match is None:
        return _tool_result(runtime, draft=state["draft"], content=f"Unknown city: {city}.")
    city = match
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

    outcome = await send_contact_verification(
        rt.services, rt.master, session_id, draft, resend=resend, actor="agent"
    )
    updated = outcome.draft
    sent, throttled, failures = outcome.sent, outcome.throttled, outcome.failures
    mobile_text = str(mobile) if mobile else None

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
    draft = state["draft"]
    # This chat's own inquiries: the current one and, after a follow-on, the earlier one.
    owned = {ref.upper(): ref for ref in (draft.reference, draft.follow_on_of) if ref}
    own = owned.get(reference.strip().upper())
    if own is None:
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


@tool
def start_follow_on(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
    mall_id: str | None = None,
) -> Command[Any]:
    """Start another inquiry for a different mall, only after this one was submitted.

    Company, brand, unit type, sales category and contact are copied for the user to
    confirm in one card, and the Company and Brand Profiles are reused. Pass mall_id
    only for a mall the user named; then ask only for anything still missing (the mall,
    if not given, and any space details).
    """
    rt = runtime_from_config(runtime.config)
    draft = state["draft"]
    reference = draft.reference
    if not reference:
        return _tool_result(
            runtime,
            draft=draft,
            content=(
                "No submitted inquiry yet, so there is nothing to follow on from. One mall "
                "per inquiry: finish and submit this one, then start another for the next mall."
            ),
        )
    previous_malls = draft.fields[FieldKey.MALLS].value
    previous_ids = [str(m) for m in previous_malls] if isinstance(previous_malls, list) else []
    mall_note = ""
    accepted: list[str] = []
    if mall_id:
        if mall_id in previous_ids:
            return _tool_result(
                runtime,
                draft=draft,
                content=(
                    f"{mall_id} is the mall of {reference}, already submitted. Ask which other "
                    "mall they'd like."
                ),
            )
        accepted, refused = filter_mall_ids([mall_id], [], _last_user_text(state), rt.master)
        if refused:
            mall_note = (
                f" Mall not saved ({mall_id}: not named by the user or unknown); ask which "
                "mall, or use show_mall_picker for the city."
            )

    policy = get_policy()
    new_draft, copied, reused = draft_ops.follow_on_draft(
        draft, reuse_hours=policy.follow_on_reuse_hours
    )
    changed = list(copied)
    if accepted:
        new_draft, written, _errors = draft_ops.write_fields(
            new_draft, [(FieldKey.MALLS.value, accepted, Source.USER)], master=rt.master
        )
        changed.extend(written)

    inquiry_seq = int(state.get("inquiry_seq", 1)) + 1
    card_id = allocate_confirm_card_id([])
    card = build_confirm_fields_card(
        new_draft,
        rt.master,
        copied,
        card_id=card_id,
        title=f"Same details as {reference}",
    )
    _emit_draft(new_draft, changed, runtime)
    _emit_card(card, runtime)
    rt.services.audit.record(
        state["session_id"],
        "follow_on_started",
        actor="agent",
        payload={
            "from_reference": reference,
            "inquiry_seq": inquiry_seq,
            "reused_verification": reused,
        },
    )

    mall_text = (
        f"for {rt.master.label_for('malls', accepted[0]) or accepted[0]}"
        if accepted
        else "with no mall yet"
    )
    verification = (
        "The contact is still verified (verified recently, unchanged)."
        if reused
        else "The contact needs verifying again (send_verification after they confirm)."
    )
    content = (
        f"follow_on_started from={reference}. A new inquiry {mall_text} is now current. "
        f"Company, brand, unit type, sales category and contact are on one card titled "
        f"'Same details as {reference}' for the user to confirm; Company Profile and Brand "
        f"Profile are reused. {verification} Ask only for what's still missing: "
        f"{'' if accepted else 'the mall, '}any space details."
        f"{mall_note}"
    )
    return Command(
        update={
            "draft": new_draft,
            "cards_shown": [card_id],
            "confirm_card_keys": {card_id: list(copied)},
            "confirm_card_turns": {card_id: state["turn_index"]},
            "inquiry_seq": inquiry_seq,
            "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id or "")],
        }
    )


@tool
def show_application_link(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Assisted mode: show the Send application link card once the basic info is complete.
    The executive presses the button; this tool never sends anything."""
    if state.get("assisted") and state.get("existing_cr_choice") == "sign_in":
        return _tool_result(
            runtime,
            draft=state["draft"],
            content=(
                "The executive asked the caller to sign in; there's no application link "
                "for this inquiry."
            ),
            cards_shown=list(state["cards_shown"]),
        )
    draft = state["draft"]
    card = build_send_link_card(draft)
    _emit_card(card, runtime)
    cards_shown = list(state["cards_shown"])
    if SEND_LINK_CARD_ID not in cards_shown:
        cards_shown.append(SEND_LINK_CARD_ID)
    if card.payload["can_send"]:
        content = (
            "Send link card shown. The basic info is complete: the executive presses Send "
            f"application link to email it to {card.payload['email_masked']}."
        )
    else:
        content = "Not ready to send yet. Still missing: " + ", ".join(card.payload["missing"])
    return _tool_result(runtime, draft=draft, content=content, cards_shown=cards_shown)


TOOLS = [
    verify_cr,
    skip_cr,
    record_cr_answer,
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
    start_follow_on,
]

# Assisted mode (intake channels §3.2): no verification, documents or review for the
# executive; the applicant does those from the application link.
ASSISTED_EXCLUDED = frozenset(
    {"send_verification", "request_documents", "show_review", "start_follow_on", "record_cr_answer"}
)
ASSISTED_TOOLS = [t for t in TOOLS if t.name not in ASSISTED_EXCLUDED] + [show_application_link]
