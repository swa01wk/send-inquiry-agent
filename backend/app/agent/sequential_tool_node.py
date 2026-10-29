"""Run multiple tool calls in order so each sees prior draft updates."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from app.agent.state import AgentState


def _apply_command(
    state: AgentState,
    output: ToolMessage | Command[Any] | list[Any],
) -> AgentState:
    items: list[Any]
    if isinstance(output, list):
        items = output
    else:
        items = [output]

    draft = state["draft"]
    cards_shown = list(state["cards_shown"])
    confirm_card_keys = dict(state.get("confirm_card_keys", {}))
    confirm_card_turns = dict(state.get("confirm_card_turns", {}))
    inquiry_seq = int(state.get("inquiry_seq", 1))
    contacts_draft = list(state.get("contacts_draft") or [])
    case_id = state.get("case_id")
    new_messages: list[BaseMessage] = []

    for item in items:
        if isinstance(item, Command):
            update = item.update or {}
            if "draft" in update:
                draft = update["draft"]
            if "cards_shown" in update:
                cards_shown = list(update["cards_shown"])
            if "confirm_card_keys" in update:
                confirm_card_keys = dict(update["confirm_card_keys"])
            if "confirm_card_turns" in update:
                confirm_card_turns = dict(update["confirm_card_turns"])
            if "inquiry_seq" in update:
                inquiry_seq = int(update["inquiry_seq"])
            if "contacts_draft" in update:
                contacts_draft = list(update["contacts_draft"])
            if "case_id" in update:
                case_id = update["case_id"]
            for message in update.get("messages", []):
                if isinstance(message, ToolMessage):
                    new_messages.append(message)
        elif isinstance(item, ToolMessage):
            new_messages.append(item)
        elif isinstance(item, dict):
            for message in item.get("messages", []):
                if isinstance(message, ToolMessage):
                    new_messages.append(message)

    merged: AgentState = {
        **state,
        "draft": draft,
        "cards_shown": cards_shown,
        "confirm_card_keys": confirm_card_keys,
        "confirm_card_turns": confirm_card_turns,
        "inquiry_seq": inquiry_seq,
        "messages": [*state["messages"], *new_messages],
    }
    if contacts_draft or "contacts_draft" in state:
        merged["contacts_draft"] = contacts_draft
    if case_id is not None:
        merged["case_id"] = case_id
    return merged


def build_sequential_tool_node(tools: list[Any]) -> Any:
    base = ToolNode(tools)

    async def sequential_tools_node(state: AgentState, config: RunnableConfig) -> Any:
        messages = state["messages"]
        if not messages:
            return {}
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls or len(last.tool_calls) == 1:
            return await base.ainvoke(state, config)

        tool_calls = last.tool_calls

        prefix = messages[:-1]
        working = state
        for call in tool_calls:
            step_state: AgentState = {
                **working,
                "messages": [
                    *prefix,
                    AIMessage(content=last.content or "", tool_calls=[call]),
                ],
            }
            output = await base.ainvoke(step_state, config)
            working = _apply_command(working, output)

        out: dict[str, Any] = {
            "draft": working["draft"],
            "cards_shown": working["cards_shown"],
            "confirm_card_keys": working.get("confirm_card_keys", {}),
            "confirm_card_turns": working.get("confirm_card_turns", {}),
            "inquiry_seq": working.get("inquiry_seq", state.get("inquiry_seq", 1)),
            "messages": working["messages"][len(state["messages"]) :],
        }
        if "contacts_draft" in working:
            out["contacts_draft"] = working["contacts_draft"]
        return out

    return sequential_tools_node
