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
    confirm_card_keys: dict[str, list[str]]
    confirm_card_turns: dict[str, int]
    turn_index: int
    guard_retries: int
    retry_agent: NotRequired[bool]


def initial_agent_state(
    *,
    session_id: str,
    draft: InquiryDraft,
    phase: str,
    turn_index: int = 0,
    confirm_card_turns: dict[str, int] | None = None,
) -> AgentState:
    return AgentState(
        messages=[],
        session_id=session_id,
        draft=draft,
        phase=phase,
        cards_shown=[],
        confirm_card_keys={},
        confirm_card_turns=dict(confirm_card_turns or {}),
        turn_index=turn_index,
        guard_retries=0,
    )
