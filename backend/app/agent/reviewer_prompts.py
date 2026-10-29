"""System prompt for the reviewer assistant (L4 §3.6)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState
from app.domain.case_brief import STAGE_LABELS, waiting_on

_PROMPT_PATH = Path(__file__).resolve().parent / "reviewer_prompt.md"


@lru_cache
def _static_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def clear_reviewer_prompt_cache() -> None:
    _static_prompt.cache_clear()


def build_reviewer_system_message(state: AgentState, config: RunnableConfig) -> SystemMessage:
    runtime = runtime_from_config(config)
    case_id = state.get("case_id")
    case = runtime.services.cases.get(case_id) if case_id else None
    if case is None:
        header = "Case record not loaded."
    else:
        queue = case.review_queue
        header = (
            f"Reference {case.reference}\n"
            f"Stage: {STAGE_LABELS.get(case.status.value, case.status.value)}\n"
            f"Waiting on: {waiting_on(case)}\n"
            f"Queue: {queue.role if queue else '—'} / {queue.region if queue else '—'}"
        )
    content = f"{_static_prompt()}\n\n## Case in view\n{header}"
    return SystemMessage(content=content)
