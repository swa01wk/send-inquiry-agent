"""LangGraph wiring for the inquiry agent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition

from app.agent.guard import after_guard, guard_node
from app.agent.model import get_chat_model
from app.agent.prompts import build_system_message
from app.agent.runtime import runtime_from_config
from app.agent.sequential_tool_node import build_sequential_tool_node
from app.agent.state import AgentState
from app.agent.tool_choice import invoke_tool_choice
from app.agent.tools import TOOLS
from app.domain.rules import compute_phase


def build_graph(
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    factory = model_factory or get_chat_model
    chat_model = factory().bind_tools(TOOLS)

    def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        runtime = runtime_from_config(config)
        system = build_system_message(state["draft"], runtime.master)
        tool_choice = invoke_tool_choice(state)
        model = chat_model.bind(**tool_choice) if tool_choice else chat_model
        response = model.invoke([system, *state["messages"]], config=config)
        phase = compute_phase(state["draft"]).value
        return {"messages": [response], "phase": phase, "retry_agent": False}

    def guard_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        runtime = runtime_from_config(config)
        return guard_node(state, runtime=runtime)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", build_sequential_tool_node(TOOLS))
    graph.add_node("guard", guard_wrapper)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": "guard"})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("guard", after_guard, {"agent": "agent", "__end__": END})

    return graph.compile(checkpointer=MemorySaver())
