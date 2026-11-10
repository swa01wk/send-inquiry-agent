"""The documents card on the upload path (re-demo flow 1, 10 Nov 2026).

After CR = no and "I'll upload the profiles", the company and brand fields come from the
profiles, so the phase stays `collecting` until they're uploaded. The guard attaches the
documents card when the user makes that choice, rather than waiting for a phase the upload
path can't reach on its own.
"""

from typing import Any
from unittest.mock import patch

from app.agent.guard import guard_node
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.rules import compute_phase
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


def _run(
    messages: list[BaseMessage],
    agent_runtime: AgentRuntime,
    cards_shown: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"  # CR = no
    state = initial_agent_state(session_id="sess-docs-card", draft=draft, phase="collecting")
    state["messages"] = messages
    state["cards_shown"] = cards_shown or []
    events: list[dict[str, Any]] = []
    with patch("app.agent.guard.get_stream_writer", return_value=events.append):
        result = guard_node(state, runtime=agent_runtime)
    return result, events


def _document_cards(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e["data"]
        for e in events
        if e["type"] == "ui_card" and e["data"]["card_type"] == "document_upload"
    ]


def test_upload_choice_attaches_the_documents_card(agent_runtime: AgentRuntime) -> None:
    assert compute_phase(new_inquiry_draft()).value != "documents"
    result, events = _run(
        [
            HumanMessage(content="[ui_event] cr_answer no"),
            AIMessage(content="Would you like to type the details or upload the profiles?"),
            HumanMessage(content="I'll upload the profiles"),
            AIMessage(content="Perfect — upload the Company Profile and Brand Profile."),
        ],
        agent_runtime,
    )
    assert result.get("retry_agent") is not True
    assert len(_document_cards(events)) == 1
    assert "documents" in result["cards_shown"]


def test_typed_choice_does_not_attach_the_documents_card(agent_runtime: AgentRuntime) -> None:
    result, events = _run(
        [
            HumanMessage(content="[ui_event] cr_answer no"),
            HumanMessage(content="I'll type them"),
            AIMessage(content="What's the company name and address?"),
        ],
        agent_runtime,
    )
    assert _document_cards(events) == []
    assert "documents" not in result["cards_shown"]


def test_documents_card_is_attached_once(agent_runtime: AgentRuntime) -> None:
    _, events = _run(
        [
            HumanMessage(content="I'll upload the profiles"),
            AIMessage(content="Great — use the documents card."),
            HumanMessage(content="A specialty coffee kiosk at Riyadh Mall A"),
            AIMessage(content="Got it. Who should we contact?"),
        ],
        agent_runtime,
        cards_shown=["documents"],
    )
    assert _document_cards(events) == []
