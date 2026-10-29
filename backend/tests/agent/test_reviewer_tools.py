"""Reviewer assistant tools: cards, Yardi rules, case record unchanged."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from app.agent.reviewer_tools import (
    REVIEWER_TOOLS,
    draft_reviewer_note,
    get_case_brief,
    list_company_brands,
    search_yardi_companies,
)
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import DocType, DocumentRef, FieldKey
from app.domain.rules import compute_phase
from app.workflow.machine import SYSTEM, Actor, transition
from app.workflow.models import Case, CaseStatus, ReviewQueue, WorkflowEvent
from tests.agent.conftest import make_tool_runtime

T0 = datetime(2026, 10, 30, 9, tzinfo=UTC)
REVIEWER = Actor(kind="reviewer", id="rlm_store-central", role="rlm_store", regions=["central"])
QUEUE = ReviewQueue(product_line="store", region="central", role="rlm_store")


def _snapshot(case: Case) -> dict[str, Any]:
    return {
        "status": case.status,
        "events": len(case.events),
        "requests": [r.model_dump(mode="json") for r in case.requests],
        "decisions": [d.model_dump(mode="json") for d in case.decisions],
        "yardi": case.yardi.model_dump(mode="json"),
    }


def _case_in_store(agent_runtime: AgentRuntime) -> Case:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.COMPANY_NAME].value = "Bean Street Trading Co."
    draft.documents[DocType.BRAND_PROFILE] = DocumentRef(
        doc_type=DocType.BRAND_PROFILE,
        file_id="b1",
        file_name="brand.pdf",
        size_bytes=9,
        uploaded_at=T0,
    )
    case = Case(
        id="GEO-STR-000099",
        reference="GEO-STR-000099",
        session_id="sess-reviewer-tools",
        status=CaseStatus.SUBMITTED,
        draft=draft,
        submitted_at=T0,
    )
    case = transition(
        case,
        WorkflowEvent(name="routed", payload={"queue": QUEUE.model_dump()}),
        actor=SYSTEM,
        now=T0,
    )
    agent_runtime.services.cases.save(case)
    return case


def _state(agent_runtime: AgentRuntime, case: Case):
    phase = compute_phase(case.draft).value
    state = initial_agent_state(
        session_id="review:GEO-STR-000099:rlm_store-central",
        draft=case.draft,
        phase=phase,
    )
    state["case_id"] = case.id
    return state


def _suggestion_cards(events: list[dict]) -> list[dict]:
    return [
        e["data"]
        for e in events
        if e.get("type") == "ui_card" and e["data"].get("card_type") == "reviewer_suggestion"
    ]


@pytest.fixture
def seeded_case(agent_runtime: AgentRuntime) -> Case:
    return _case_in_store(agent_runtime)


@pytest.fixture
def reviewer_state(agent_runtime: AgentRuntime, seeded_case: Case):
    return _state(agent_runtime, seeded_case)


def test_reviewer_allowlist_has_no_case_mutators() -> None:
    names = {t.name for t in REVIEWER_TOOLS}
    assert names == {
        "get_case_brief",
        "search_yardi_companies",
        "list_company_brands",
        "draft_reviewer_note",
    }


def test_get_case_brief_text(agent_runtime, reviewer_state, seeded_case, stream_events):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=reviewer_state, agent_runtime=agent_runtime, writer=writer)
    result = get_case_brief.invoke({"state": reviewer_state, "runtime": runtime})
    text = result.update["messages"][0].content
    assert seeded_case.reference in text
    assert "Bean Street Trading Co." in text
    assert "Next decision checklist:" in text
    assert not _suggestion_cards(events)
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_search_yardi_companies_first_word_and_cards(
    agent_runtime, reviewer_state, seeded_case, stream_events
):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=reviewer_state, agent_runtime=agent_runtime, writer=writer)
    result = search_yardi_companies.invoke(
        {"name": "Bean Street Trading Co.", "state": reviewer_state, "runtime": runtime}
    )
    body = result.update["messages"][0].content
    assert "Bean Street Trading Co." in body
    assert "first word 'bean'" in body.lower()
    assert "Bean & Leaf" not in body  # inactive company
    cards = _suggestion_cards(events)
    assert len(cards) >= 2
    assert all(c["payload"]["action"] == "relink_company" for c in cards)
    assert any(c["payload"]["payload"].get("company_id") == "YC-1001" for c in cards)
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_list_company_brands(agent_runtime, reviewer_state, seeded_case, stream_events):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=reviewer_state, agent_runtime=agent_runtime, writer=writer)
    result = list_company_brands.invoke(
        {"company_id": "YC-1001", "state": reviewer_state, "runtime": runtime}
    )
    body = result.update["messages"][0].content
    assert "Bean Street" in body
    assert "YB-2001" in body
    cards = _suggestion_cards(events)
    assert len(cards) == 2
    assert all(c["payload"]["action"] == "relink_brand" for c in cards)
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_draft_reviewer_note_emits_card(agent_runtime, reviewer_state, seeded_case, stream_events):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=reviewer_state, agent_runtime=agent_runtime, writer=writer)
    result = draft_reviewer_note.invoke(
        {
            "kind": "reupload_remarks",
            "points": ["Logo page is missing from the brand profile."],
            "state": reviewer_state,
            "runtime": runtime,
        }
    )
    text = result.update["messages"][0].content
    assert "Logo page" in text
    cards = _suggestion_cards(events)
    assert len(cards) == 1
    card = cards[0]["payload"]
    assert card["kind"] == "reupload_remarks"
    assert card["action"] == "request_reupload"
    assert "Logo page" in card["payload"]["remarks"]
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before
