"""System prompt for the case assistant (L4 §3.5)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import SystemMessage

from app.agent.runtime import AgentRuntime
from app.agent.state import AgentState
from app.api.case_cards import _STAGE_LABELS
from app.policy.config import get_policy
from app.services.status import REQUEST_LABELS, _from_case
from app.workflow.models import Case, TenantContact

_PROMPT_PATH = Path(__file__).resolve().parent / "case_prompt.md"


@lru_cache
def _static_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def clear_case_prompt_cache() -> None:
    _static_prompt.cache_clear()


def _case(runtime: AgentRuntime, state: AgentState) -> Case | None:
    case_id = state.get("case_id")
    if not case_id:
        return None
    return runtime.services.cases.get(case_id)


def _contacts_summary(contacts: list[dict[str, Any]]) -> str:
    if not contacts:
        return "No additional contacts drafted yet."
    lines: list[str] = []
    for raw in contacts:
        contact = TenantContact.model_validate(raw)
        name = " ".join(
            p for p in (contact.first_name.value, contact.last_name.value) if p not in (None, "")
        )
        flag = " (same as primary)" if contact.same_as_primary else ""
        lines.append(f"- {contact.role}{flag}: {name or 'incomplete'}")
    return "\n".join(lines)


def build_case_system_message(state: AgentState, runtime: AgentRuntime) -> SystemMessage:
    policy = get_policy()
    rules = [
        "## Rules in force",
        f"- After rejection: {policy.after_rejection}",
        "- Required additional contacts: "
        + ", ".join(policy.second_level_contacts.required)
        + ". Optional: "
        + ", ".join(policy.second_level_contacts.optional)
        + ".",
    ]
    case = _case(runtime, state)
    status_block = "Case record not loaded (missing case_id)."
    if case is not None:
        status = _from_case(case)
        stage_label = _STAGE_LABELS.get(status.current_stage, status.current_stage)
        open_lines = [
            f"  - {REQUEST_LABELS[r.kind]}: {r.remarks}"
            for r in case.requests
            if r.status == "open"
        ]
        open_text = "\n".join(open_lines) if open_lines else "  - none"
        status_block = (
            f"Reference {case.reference}\n"
            f"Stage: {stage_label}\n"
            f"Owner role: {status.owner_role}\n"
            f"Open requests:\n{open_text}"
        )
    contacts = state.get("contacts_draft") or []
    content = (
        f"{_static_prompt()}\n\n"
        f"{chr(10).join(rules)}\n\n"
        f"## Current case\n{status_block}\n\n"
        f"## Contacts draft\n{_contacts_summary(contacts)}"
    )
    return SystemMessage(content=content)
