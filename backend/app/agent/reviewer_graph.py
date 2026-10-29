"""LangGraph wiring for the reviewer assistant (L4 §3.6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph import build_agent_graph
from app.agent.model import get_chat_model
from app.agent.reviewer_guard import reviewer_guard_node
from app.agent.reviewer_prompts import build_reviewer_system_message
from app.agent.reviewer_tools import REVIEWER_TOOLS
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState


def build_reviewer_graph(
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    factory = model_factory or get_chat_model

    def system_for_turn(state: AgentState, config: RunnableConfig) -> Any:
        return build_reviewer_system_message(state, config)

    def guard(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        return reviewer_guard_node(state, runtime=runtime_from_config(config))

    return build_agent_graph(
        tools=REVIEWER_TOOLS,
        system_for_turn=system_for_turn,
        guard_node_fn=guard,
        model_factory=factory,
    )
