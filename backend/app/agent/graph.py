"""LangGraph wiring for the inquiry agent."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition

from app.agent.guard import after_guard, guard_node
from app.agent.model import ModelUnavailable, get_chat_model, model_error_kind
from app.agent.prompts import build_system_message, channel_notes
from app.agent.runtime import AgentRuntime, runtime_from_config
from app.agent.sequential_tool_node import build_sequential_tool_node
from app.agent.state import AgentState
from app.agent.tools import ASSISTED_TOOLS, TOOLS
from app.domain.rules import compute_phase
from app.gateway import GatewayError

logger = logging.getLogger(__name__)


MODEL_ATTEMPTS = 2


def _invoke_model(
    chat_model: Any,
    messages: list[Any],
    config: RunnableConfig,
    runtime: AgentRuntime,
    session_id: str,
) -> Any:
    """Call the model through the gateway; two failures in a row → ModelUnavailable.

    `FORM_MODE=true` (testing) treats the model as down without calling it. Faults for
    tests come from `MOCK_FAULTS` / `X-Mock-Faults` with service `llm`.
    """
    if runtime.settings.form_mode:
        raise ModelUnavailable("unavailable")
    kind = "unavailable"
    for _attempt in range(MODEL_ATTEMPTS):
        try:
            return runtime.services.gateway.call_sync(
                "llm", "invoke", chat_model.invoke, messages, config=config, inquiry_id=session_id
            )
        except GatewayError as err:
            if err.kind == "invalid":
                # A ValueError from our own code is a bug, not an outage: surface it.
                raise err.__cause__ or err from None
            kind = "timeout" if err.kind == "timeout" else "unavailable"
        except Exception as exc:
            provider_kind = model_error_kind(exc)
            if provider_kind is None:
                raise
            logger.warning("model call failed (%s): %s", provider_kind, type(exc).__name__)
            kind = provider_kind
    raise ModelUnavailable(kind)


def build_agent_graph(
    *,
    tools: list[Any],
    system_for_turn: Callable[[AgentState, RunnableConfig], SystemMessage],
    guard_node_fn: Callable[[AgentState, RunnableConfig], dict[str, Any]],
    model_factory: Callable[[], BaseChatModel],
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    default_model = model_factory().bind_tools(tools)

    def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        runtime = runtime_from_config(config)
        configurable = config.get("configurable") or {}
        chat_model = configurable.get("bound_chat_model") or default_model
        system = system_for_turn(state, config)
        response = _invoke_model(
            chat_model, [system, *state["messages"]], config, runtime, state["session_id"]
        )
        phase = compute_phase(state["draft"]).value
        return {"messages": [response], "phase": phase, "retry_agent": False}

    def guard_wrapper(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        return guard_node_fn(state, config)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", build_sequential_tool_node(tools))
    graph.add_node("guard", guard_wrapper)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", "__end__": "guard"})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("guard", after_guard, {"agent": "agent", "__end__": END})

    return graph.compile(checkpointer=MemorySaver())


def system_for_turn(state: AgentState, config: RunnableConfig) -> SystemMessage:
    """The intake prompt, plus the channel's notes (assisted, existing tenant)."""
    runtime = runtime_from_config(config)
    message = build_system_message(state["draft"], runtime.master, state["cards_shown"])
    notes = channel_notes(state.get("channel"), bool(state.get("assisted")))
    return SystemMessage(content=f"{message.content}\n\n{notes}") if notes else message


def guard(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    return guard_node(state, runtime=runtime_from_config(config))


def build_graph(
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    factory = model_factory or get_chat_model

    return build_agent_graph(
        tools=TOOLS,
        system_for_turn=system_for_turn,
        guard_node_fn=guard,
        model_factory=factory,
    )


def build_assisted_graph(
    model_factory: Callable[[], BaseChatModel] | None = None,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Assisted mode (intake channels §3.2): the intake agent with the assisted allowlist."""
    return build_agent_graph(
        tools=ASSISTED_TOOLS,
        system_for_turn=system_for_turn,
        guard_node_fn=guard,
        model_factory=model_factory or get_chat_model,
    )
