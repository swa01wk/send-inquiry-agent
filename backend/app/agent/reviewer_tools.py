"""Tools for the reviewer assistant (L4 §3.6): read-only; suggestions via cards only."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState, ToolRuntime
from langgraph.types import Command

from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.api.schemas import UiCard
from app.domain.case_brief import build_case_brief, format_case_brief_text
from app.workflow.models import Case

NOTE_KIND = Literal[
    "reupload_remarks",
    "rejection_remarks",
    "contacts_request",
    "tenant_reminder",
]

NOTE_ACTION: dict[str, str] = {
    "reupload_remarks": "request_reupload",
    "rejection_remarks": "reject",
    "contacts_request": "request_contacts",
    # Proactive reminders (L5): text only until the attention UI wires a send action.
    "tenant_reminder": "",
}

__all__ = [
    "REVIEWER_TOOLS",
    "get_case_brief",
    "search_yardi_companies",
    "list_company_brands",
    "draft_reviewer_note",
]


def _case(state: AgentState, runtime: ToolRuntime) -> Case | None:
    case_id = state.get("case_id")
    if not case_id:
        return None
    return runtime_from_config(runtime.config).services.cases.get(case_id)


def _emit_suggestion(
    runtime: ToolRuntime,
    *,
    kind: str,
    action: str,
    payload: dict[str, Any],
    text: str,
) -> None:
    card = UiCard(
        card_id=f"reviewer-suggest-{uuid.uuid4().hex[:10]}",
        card_type="reviewer_suggestion",
        payload={
            "kind": kind,
            "action": action,
            "payload": payload,
            "text": text,
        },
    )
    runtime.stream_writer({"type": "ui_card", "data": card.model_dump()})


def _tool_message(runtime: ToolRuntime, content: str) -> Command[Any]:
    return Command(
        update={
            "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id or "")],
        }
    )


def _first_word(name: str) -> str:
    words = name.strip().split()
    return words[0].lower().strip(".,&") if words else ""


def _draft_text(kind: NOTE_KIND, points: list[str]) -> str:
    body = "\n".join(f"• {point.strip()}" for point in points if point.strip())
    if kind == "reupload_remarks":
        return f"Please update and re-upload the following:\n{body}"
    if kind == "rejection_remarks":
        return f"After review we are unable to proceed:\n{body}"
    if kind == "contacts_request":
        return (
            "Please provide the following company contacts "
            "(Authorized Signatory and Billing Contact are required):\n"
            f"{body}"
        )
    return f"Reminder — action needed on your inquiry:\n{body}"


@tool
def get_case_brief(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Return the deterministic case brief as plain text."""
    rt = runtime_from_config(runtime.config)
    case = _case(state, runtime)
    if case is None:
        return _tool_message(runtime, "No case linked to this thread.")
    brief = build_case_brief(case, rt.master)
    text = format_case_brief_text(brief)
    return _tool_message(runtime, text)


@tool
def search_yardi_companies(
    name: str,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Search active Yardi companies by the first word of the company name."""
    rt = runtime_from_config(runtime.config)
    if _case(state, runtime) is None:
        return _tool_message(runtime, "No case linked to this thread.")
    needle = _first_word(name)
    matches = rt.services.yardi.search_companies(name)
    if not matches:
        return _tool_message(
            runtime,
            f"No active Yardi companies matched the first word '{needle}'.",
        )
    lines: list[str] = []
    for company in matches:
        reason = f"First word '{needle}' matches a word in the company name."
        line = f"{company.name} (id {company.id}) — {reason}"
        lines.append(line)
        _emit_suggestion(
            runtime,
            kind="yardi_company",
            action="relink_company",
            payload={"company_id": company.id},
            text=line,
        )
    return _tool_message(runtime, "\n".join(lines))


@tool
def list_company_brands(
    company_id: str,
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """List brands from the company's previous leases and proposals."""
    rt = runtime_from_config(runtime.config)
    if _case(state, runtime) is None:
        return _tool_message(runtime, "No case linked to this thread.")
    company = rt.services.yardi.company(company_id)
    if company is None:
        return _tool_message(runtime, f"Unknown Yardi company id {company_id}.")
    brands = rt.services.yardi.brands_for_company(company_id)
    if not brands:
        return _tool_message(runtime, f"No brands on record for {company.name}.")
    lines: list[str] = []
    for brand in brands:
        line = f"{brand.name} (id {brand.id}, from {brand.source})"
        lines.append(line)
        _emit_suggestion(
            runtime,
            kind="yardi_brand",
            action="relink_brand",
            payload={"brand_id": brand.id},
            text=line,
        )
    return _tool_message(runtime, "\n".join(lines))


@tool
def draft_reviewer_note(
    kind: NOTE_KIND,
    points: list[str],
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Draft remarks for a reviewer action form (does not send anything)."""
    if _case(state, runtime) is None:
        return _tool_message(runtime, "No case linked to this thread.")
    if not points:
        return _tool_message(runtime, "Provide at least one point for the draft.")
    text = _draft_text(kind, points)
    action = NOTE_ACTION[kind]
    _emit_suggestion(
        runtime,
        kind=kind,
        action=action,
        payload={"remarks": text},
        text=text,
    )
    return _tool_message(runtime, text)


REVIEWER_TOOLS = [
    get_case_brief,
    search_yardi_companies,
    list_company_brands,
    draft_reviewer_note,
]
