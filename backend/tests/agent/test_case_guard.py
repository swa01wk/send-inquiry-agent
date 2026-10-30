"""Case assistant guard: outcome claims vs ui_events and case status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.agent.case_guard import (
    _APPROVAL_CLAIM_RE,
    _CONTACTS_SENT_RE,
    _DOC_RESUBMITTED_RE,
    _contacts_card_missing_note,
    _false_outcome_note,
)
from app.agent.runtime import AgentRuntime
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import DocType, DocumentRef
from app.workflow.machine import SYSTEM, Actor, transition
from app.workflow.models import Case, CaseStatus, ReviewQueue, WorkflowEvent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

T0 = datetime(2026, 10, 30, 9, tzinfo=UTC)
REVIEWER = Actor(kind="reviewer", id="rlm_store-central", role="rlm_store", regions=["central"])
QUEUE = ReviewQueue(product_line="store", region="central", role="rlm_store")


@pytest.mark.parametrize(
    "text",
    [
        "The leasing team sent back your Brand Profile because the logo page is missing.",
        "We have sent an invitation to your email so you can sign in.",
        "Your inquiry has been approved at the first level.",
    ],
)
def test_benign_replies_do_not_match_outcome_patterns(text: str) -> None:
    assert not _DOC_RESUBMITTED_RE.search(text)
    assert not _CONTACTS_SENT_RE.search(text)


def test_contacts_sent_claim_matches() -> None:
    assert _CONTACTS_SENT_RE.search("Your contacts have been sent.")


@pytest.mark.parametrize(
    "text",
    [
        "The leasing team sent back your Brand Profile because the logo page is missing.",
        "We have sent an invitation to your email so you can sign in.",
    ],
)
def test_false_outcome_note_ignores_benign_sent_wording(
    agent_runtime: AgentRuntime, text: str
) -> None:
    case = _reupload_case(agent_runtime)
    turn = [HumanMessage(content="?"), AIMessage(content=text)]
    assert _false_outcome_note(text, turn, case) is None


def _reupload_case(agent_runtime: AgentRuntime) -> Case:
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
        session_id="sess-guard",
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
    case = transition(
        case,
        WorkflowEvent(
            name="reupload_requested",
            payload={"doc_types": ["brand_profile"], "remarks": "Update logo."},
        ),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=1),
    )
    agent_runtime.services.cases.save(case)
    return case


def _second_review_case(agent_runtime: AgentRuntime) -> Case:
    draft = new_inquiry_draft()
    draft.documents[DocType.BRAND_PROFILE] = DocumentRef(
        doc_type=DocType.BRAND_PROFILE,
        file_id="b1",
        file_name="brand.pdf",
        size_bytes=9,
        uploaded_at=T0,
    )
    case = Case(
        id="GEO-STR-000088",
        reference="GEO-STR-000088",
        session_id="sess-guard-2",
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
    case = transition(
        case,
        WorkflowEvent(name="approved_first", payload={}),
        actor=REVIEWER,
        now=T0 + timedelta(minutes=1),
    )
    agent_runtime.services.cases.save(case)
    return case


def test_false_outcome_note_flags_contacts_sent_without_ui_event(
    agent_runtime: AgentRuntime,
) -> None:
    case = _reupload_case(agent_runtime)
    turn = [
        HumanMessage(content="Are my contacts in?"),
        AIMessage(content="Your contacts have been sent."),
    ]
    note = _false_outcome_note("Your contacts have been sent.", turn, case)
    assert note is not None


def test_false_outcome_note_allows_first_level_approval_in_second_review(
    agent_runtime: AgentRuntime,
) -> None:
    case = _second_review_case(agent_runtime)
    text = "Your inquiry has been approved at the first level."
    turn = [HumanMessage(content="Where am I?"), AIMessage(content=text)]
    assert _APPROVAL_CLAIM_RE.search(text)
    note = _false_outcome_note(text, turn, case)
    assert note is None


def test_false_outcome_note_skipped_when_contacts_submitted_ui_event(
    agent_runtime: AgentRuntime,
) -> None:
    case = _reupload_case(agent_runtime)
    turn = [
        HumanMessage(content="[ui_event] contacts_submitted"),
        AIMessage(content="Your contacts have been sent."),
    ]
    note = _false_outcome_note("Your contacts have been sent.", turn, case)
    assert note is None


def _contacts_request_case(agent_runtime: AgentRuntime) -> Case:
    case = _second_review_case(agent_runtime)
    case = transition(
        case,
        WorkflowEvent(name="contacts_requested", payload={"remarks": ""}),
        actor=SYSTEM,
        now=T0 + timedelta(minutes=2),
    )
    agent_runtime.services.cases.save(case)
    return case


_BOTH_ROLES = [{"role": "authorized_signatory"}, {"role": "billing_contact"}]


def _contacts_turn(*tool_names: str, result: str = "Contacts draft updated (2 role(s)).") -> list:
    calls = [{"name": n, "args": {}, "id": f"call-{i}"} for i, n in enumerate(tool_names)]
    turn: list = [
        HumanMessage(content="I'm the signatory; billing is Omar Saleh, omar@x.sa, +966551234567"),
        AIMessage(content="", tool_calls=calls),
    ]
    for i, name in enumerate(tool_names):
        content = result if name == "update_contacts" else "Contacts review card shown."
        turn.append(ToolMessage(content=content, tool_call_id=f"call-{i}"))
    turn.append(AIMessage(content="I've put you down as Authorized Signatory."))
    return turn


def test_contacts_card_missing_note_when_saved_without_card(agent_runtime: AgentRuntime) -> None:
    case = _contacts_request_case(agent_runtime)
    note = _contacts_card_missing_note(_contacts_turn("update_contacts"), case, _BOTH_ROLES)
    assert note is not None
    assert "show_contacts_review" in note


def test_contacts_card_missing_note_quiet_when_card_shown(agent_runtime: AgentRuntime) -> None:
    case = _contacts_request_case(agent_runtime)
    turn = _contacts_turn("update_contacts", "show_contacts_review")
    assert _contacts_card_missing_note(turn, case, _BOTH_ROLES) is None


def test_contacts_card_missing_note_quiet_on_validation_errors(agent_runtime: AgentRuntime) -> None:
    case = _contacts_request_case(agent_runtime)
    turn = _contacts_turn("update_contacts", result="Contact validation errors: billing: email")
    assert _contacts_card_missing_note(turn, case, _BOTH_ROLES) is None


def test_contacts_card_missing_note_quiet_until_required_roles(agent_runtime: AgentRuntime) -> None:
    case = _contacts_request_case(agent_runtime)
    turn = _contacts_turn("update_contacts")
    assert _contacts_card_missing_note(turn, case, [{"role": "authorized_signatory"}]) is None


def test_contacts_card_missing_note_quiet_without_open_request(agent_runtime: AgentRuntime) -> None:
    case = _second_review_case(agent_runtime)
    note = _contacts_card_missing_note(_contacts_turn("update_contacts"), case, _BOTH_ROLES)
    assert note is None
