"""LangGraph wiring for the case assistant (L4 §3.5)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agent.case_guard import case_guard_node
from app.agent.case_prompts import build_case_system_message
from app.agent.case_tools import CASE_TOOLS
from app.agent.graph import build_agent_graph
from app.agent.model import get_chat_model
from app.agent.runtime import runtime_from_config
from app.agent.state import AgentState


def build_case_graph(
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    factory = model_factory or get_chat_model

    def system_for_turn(state: AgentState, config: RunnableConfig) -> SystemMessage:
        runtime = runtime_from_config(config)
        return build_case_system_message(state, runtime)

    def guard(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        return case_guard_node(state, runtime=runtime_from_config(config))

    return build_agent_graph(
        tools=CASE_TOOLS,
        system_for_turn=system_for_turn,
        guard_node_fn=guard,
        model_factory=factory,
    )
