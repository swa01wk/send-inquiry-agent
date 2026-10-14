"""LangGraph agent state."""

from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.domain.models import InquiryDraft


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    draft: InquiryDraft
    phase: str
    cards_shown: list[str]
    guard_retries: int
    retry_agent: NotRequired[bool]


def initial_agent_state(*, session_id: str, draft: InquiryDraft, phase: str) -> AgentState:
    return AgentState(
        messages=[],
        session_id=session_id,
        draft=draft,
        phase=phase,
        cards_shown=[],
        guard_retries=0,
    )
