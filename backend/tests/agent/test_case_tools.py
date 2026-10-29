"""Case assistant tools: cards emitted, contacts errors, case record unchanged."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.agent.case_tools import (
    get_case_status,
    request_reupload_documents,
    request_sales_data_upload,
    show_contacts_review,
    update_contacts,
)
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import DocType, DocumentRef
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
        "tenant_contacts": [c.model_dump(mode="json") for c in case.tenant_contacts],
    }


def _case_in_store(agent_runtime: AgentRuntime, *, with_reupload: bool = False) -> Case:
    draft = new_inquiry_draft()
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
        session_id="sess-case-tools",
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
    if with_reupload:
        case = transition(
            case,
            WorkflowEvent(
                name="reupload_requested",
                payload={
                    "doc_types": ["brand_profile"],
                    "remarks": "Please send an updated brand profile.",
                },
            ),
            actor=REVIEWER,
            now=T0 + timedelta(minutes=1),
        )
    agent_runtime.services.cases.save(case)
    return case


def _case_state(agent_runtime: AgentRuntime, case: Case) -> dict:
    phase = compute_phase(case.draft).value
    state = initial_agent_state(
        session_id="sess-case-tools",
        draft=case.draft,
        phase=phase,
    )
    state["case_id"] = case.id
    state["contacts_draft"] = []
    return state


def _card_types(events: list[dict]) -> list[str]:
    return [e["data"]["card_type"] for e in events if e.get("type") == "ui_card"]


@pytest.fixture
def seeded_case(agent_runtime: AgentRuntime) -> Case:
    return _case_in_store(agent_runtime, with_reupload=True)


@pytest.fixture
def case_state(agent_runtime: AgentRuntime, seeded_case: Case):
    return _case_state(agent_runtime, seeded_case)


def test_get_case_status_emits_card(agent_runtime, case_state, seeded_case, stream_events):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=case_state, agent_runtime=agent_runtime, writer=writer)
    result = get_case_status.invoke({"state": case_state, "runtime": runtime})
    assert "case_status" in _card_types(events)
    summary = result.update["messages"][0].content
    assert "Current stage:" in summary
    assert "Brand Profile" in summary
    assert "Please send an updated brand profile." in summary
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_get_case_status_summary_includes_rejection_remarks(agent_runtime, stream_events) -> None:
    draft = new_inquiry_draft()
    case = Case(
        id="GEO-STR-000088",
        reference="GEO-STR-000088",
        session_id="sess-rejected",
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
    reject_remarks = "No kiosk space at this mall this year"
    case = transition(
        case,
        WorkflowEvent(
            name="rejected",
            payload={"remarks": reject_remarks, "reason_category": "no_space"},
        ),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=2),
    )
    agent_runtime.services.cases.save(case)
    state = _case_state(agent_runtime, case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = get_case_status.invoke({"state": state, "runtime": runtime})
    summary = result.update["messages"][0].content
    assert reject_remarks in summary
    assert "Outcome: rejected." in summary
    assert "After rejection:" in summary


def test_request_reupload_documents_emits_card(
    agent_runtime, case_state, seeded_case, stream_events
):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=case_state, agent_runtime=agent_runtime, writer=writer)
    result = request_reupload_documents.invoke({"state": case_state, "runtime": runtime})
    assert "document_upload" in _card_types(events)
    upload_events = [e for e in events if e["data"]["card_type"] == "document_upload"]
    payload = upload_events[0]["data"]["payload"]
    assert payload["mode"] == "reupload"
    assert "Brand Profile" in result.update["messages"][0].content
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_update_contacts_returns_errors_to_model(
    agent_runtime, case_state, seeded_case, stream_events
):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=case_state, agent_runtime=agent_runtime, writer=writer)
    result = update_contacts.invoke(
        {
            "entries": [{"role": "billing_contact", "email": "not-an-email"}],
            "state": case_state,
            "runtime": runtime,
        }
    )
    assert "validation errors" in result.update["messages"][0].content.lower()
    assert "billing_contact.email" in result.update["messages"][0].content
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_update_contacts_same_as_primary(agent_runtime, case_state, seeded_case, stream_events):
    before = _snapshot(seeded_case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=case_state, agent_runtime=agent_runtime, writer=writer)
    result = update_contacts.invoke(
        {
            "entries": [{"role": "authorized_signatory", "same_as_primary": True}],
            "state": case_state,
            "runtime": runtime,
        }
    )
    assert "errors" not in result.update["messages"][0].content.lower()
    draft = result.update["contacts_draft"]
    assert draft[0]["same_as_primary"] is True
    after = agent_runtime.services.cases.get(seeded_case.id)
    assert after is not None
    assert _snapshot(after) == before


def _second_review_case(agent_runtime: AgentRuntime) -> Case:
    case = _case_in_store(agent_runtime, with_reupload=False)
    case = transition(
        case,
        WorkflowEvent(name="approved_first", payload={}),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=1),
    )
    return case


def test_show_contacts_review_emits_card(agent_runtime, stream_events):
    case = _second_review_case(agent_runtime)
    case = transition(
        case,
        WorkflowEvent(
            name="contacts_requested",
            payload={"remarks": "Need signatory and billing."},
        ),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=2),
    )
    agent_runtime.services.cases.save(case)
    state = _case_state(agent_runtime, case)
    before = _snapshot(case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    show_contacts_review.invoke({"state": state, "runtime": runtime})
    assert "contacts" in _card_types(events)
    after = agent_runtime.services.cases.get(case.id)
    assert after is not None
    assert _snapshot(after) == before


def test_request_sales_data_upload_emits_card(agent_runtime, stream_events):
    case = _second_review_case(agent_runtime)
    case = transition(
        case,
        WorkflowEvent(
            name="sales_data_requested",
            payload={"remarks": "Upload last year's estimated sales."},
        ),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=2),
    )
    agent_runtime.services.cases.save(case)
    state = _case_state(agent_runtime, case)
    before = _snapshot(case)
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    request_sales_data_upload.invoke({"state": state, "runtime": runtime})
    assert "sales_data_upload" in _card_types(events)
    after = agent_runtime.services.cases.get(case.id)
    assert after is not None
    assert _snapshot(after) == before
