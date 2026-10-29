"""Tools for the case assistant (L4 §3.5): read the case and show cards only."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState, ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel

from app.agent.handoff import start_handoff
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.agent.tools import search_faq, suggest_replies
from app.api.case_cards import (
    _STAGE_LABELS,
    build_case_status_card,
    build_contacts_card,
    build_reupload_card,
    build_sales_data_card,
)
from app.api.schemas import UiCard
from app.domain.fields import document_label
from app.policy.config import get_policy
from app.services.status import REQUEST_LABELS, _from_case
from app.workflow.contacts import write_contacts
from app.workflow.models import Case, TenantContact

# Re-export shared tools for the case allowlist.
__all__ = [
    "CASE_TOOLS",
    "get_case_status",
    "request_reupload_documents",
    "update_contacts",
    "show_contacts_review",
    "request_sales_data_upload",
    "search_faq",
    "suggest_replies",
    "request_handoff",
]


def _case(state: AgentState, runtime: ToolRuntime) -> Case | None:
    case_id = state.get("case_id")
    if not case_id:
        return None
    return runtime_from_config(runtime.config).services.cases.get(case_id)


def _emit_card(card: UiCard, runtime: ToolRuntime) -> None:
    runtime.stream_writer({"type": "ui_card", "data": card.model_dump()})


def _tool_message(runtime: ToolRuntime, content: str, **update: Any) -> Command[Any]:
    return Command(
        update={
            **update,
            "messages": [ToolMessage(content=content, tool_call_id=runtime.tool_call_id or "")],
        }
    )


def _status_summary(case: Case) -> str:
    status = _from_case(case)
    stage_label = _STAGE_LABELS.get(status.current_stage, status.current_stage)
    parts = [
        f"Reference {case.reference}. Current stage: {stage_label}. "
        f"Owner role: {status.owner_role}.",
    ]
    if status.status == "rejected":
        parts.append("Outcome: rejected.")
        decision = case.decisions[-1] if case.decisions else None
        if decision and decision.remarks:
            parts.append(f"Outcome remarks: {decision.remarks}")
        parts.append(f"After rejection: {get_policy().after_rejection}")
    elif status.status in ("approved", "sent_to_yardi"):
        parts.append(f"Outcome: {status.status}.")
    open_any = False
    for request in case.requests:
        if request.status != "open":
            continue
        open_any = True
        label = REQUEST_LABELS.get(request.kind, request.kind)
        remark = (request.remarks or "").strip()
        doc_labels = ", ".join(document_label(d) for d in request.doc_types)
        chunk = f"Open {label}"
        if doc_labels:
            chunk += f" — documents: {doc_labels}"
        if remark:
            chunk += f" — remarks: {remark}"
        parts.append(chunk + ".")
    if not open_any and status.status != "rejected":
        parts.append("No open requests on the case.")
    return " ".join(parts)


class ContactEntry(BaseModel):
    role: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    contact_number: str | None = None
    same_as_primary: bool = False
    source: Literal["derived"] | None = None


@tool
def get_case_status(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show the case status card and return a short summary for the model."""
    case = _case(state, runtime)
    if case is None:
        return _tool_message(runtime, "No case linked to this session.")
    card = build_case_status_card(case)
    _emit_card(card, runtime)
    return _tool_message(runtime, _status_summary(case))


@tool
def request_reupload_documents(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show the document re-upload card for the open re-upload request."""
    rt = runtime_from_config(runtime.config)
    case = _case(state, runtime)
    if case is None:
        return _tool_message(runtime, "No case linked to this session.")
    request = case.open_request("reupload")
    if request is None:
        return _tool_message(runtime, "There is no open re-upload request on this case.")
    card = build_reupload_card(state["draft"], request, rt.master, max_mb=rt.settings.max_upload_mb)
    _emit_card(card, runtime)
    return _tool_message(
        runtime,
        f"Re-upload card shown for: {', '.join(document_label(d) for d in request.doc_types)}.",
    )


@tool
def update_contacts(
    entries: list[ContactEntry],
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Apply contact entries to the session contacts draft; return validation errors."""
    current = [TenantContact.model_validate(c) for c in state.get("contacts_draft") or []]
    payload = [e.model_dump(exclude_none=True) for e in entries]
    contacts, errors = write_contacts(current, payload, state["draft"])
    serialized = [c.model_dump(mode="json") for c in contacts]
    if errors:
        parts = "; ".join(f"{key}: {msg}" for key, msg in sorted(errors.items()))
        return _tool_message(
            runtime,
            f"Contact validation errors: {parts}",
            contacts_draft=serialized,
        )
    return _tool_message(
        runtime,
        f"Contacts draft updated ({len(contacts)} role(s)).",
        contacts_draft=serialized,
    )


@tool
def show_contacts_review(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show the contacts review card for the open contacts request."""
    case = _case(state, runtime)
    if case is None:
        return _tool_message(runtime, "No case linked to this session.")
    request = case.open_request("contacts")
    contacts = [TenantContact.model_validate(c) for c in state.get("contacts_draft") or []]
    card = build_contacts_card(contacts, request)
    _emit_card(card, runtime)
    if request is None:
        return _tool_message(runtime, "Contacts card shown (no open contacts request).")
    return _tool_message(runtime, "Contacts review card shown.")


@tool
def request_sales_data_upload(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
) -> Command[Any]:
    """Show the estimated sales data upload card."""
    rt = runtime_from_config(runtime.config)
    case = _case(state, runtime)
    if case is None:
        return _tool_message(runtime, "No case linked to this session.")
    request = case.open_request("sales_data")
    if request is None:
        return _tool_message(runtime, "There is no open sales data request on this case.")
    card = build_sales_data_card(state["draft"], request, max_mb=rt.settings.max_upload_mb)
    _emit_card(card, runtime)
    return _tool_message(runtime, "Sales data upload card shown.")


@tool
async def request_handoff(
    state: Annotated[AgentState, InjectedState],
    runtime: ToolRuntime,
    reason: Literal["user_asked", "model_unavailable"] | None = None,
) -> Command[Any]:
    """Connect the applicant with the call centre (handoff card)."""
    rt = runtime_from_config(runtime.config)
    picked = reason if reason in ("user_asked", "model_unavailable") else "user_asked"
    recent: list[str] = []
    for message in state["messages"]:
        if isinstance(message, HumanMessage):
            text = message.content if isinstance(message.content, str) else str(message.content)
            if not text.startswith("[ui_event]"):
                recent.append(text)
    result = await start_handoff(
        session_id=state["session_id"],
        inquiry_seq=int(state.get("inquiry_seq", 1)),
        draft=state["draft"],
        recent_user_messages=recent,
        reason=picked,
        runtime=rt,
        via="tool",
    )
    if result.card is not None:
        _emit_card(result.card, runtime)
    note = str(result.note)
    if note.startswith("[ui_event]"):
        note = note.removeprefix("[ui_event]").strip()
    return _tool_message(runtime, note)


CASE_TOOLS = [
    get_case_status,
    request_reupload_documents,
    update_contacts,
    show_contacts_review,
    request_sales_data_upload,
    search_faq,
    suggest_replies,
    request_handoff,
]
