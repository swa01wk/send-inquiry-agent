"""Chart steps in code (flow v2 §3.1, ADR-V2): which chart nodes each lifecycle event reaches,
and the machine rows of the new second level (§3.7) as pure calls."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, FieldValue, Source
from app.workflow.flow import IGNORED_NODES, FlowNode, transition_steps
from app.workflow.machine import (
    IllegalTransition,
    lead_approval_blockers,
    legal_events,
    transition,
)
from app.workflow.models import (
    AssignedUnit,
    Case,
    CaseRequest,
    CaseStatus,
    ReviewQueue,
    WorkflowEvent,
)
from tests.lifecycle.test_machine import CENTRAL_STORE

pytestmark = pytest.mark.lead_approval

T0 = datetime(2026, 11, 14, 9, tzinfo=UTC)
N = FlowNode


def _case(status: CaseStatus, product_line: str = "store") -> Case:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.MALLS] = FieldValue(value=["riyadh-mall-a"], source=Source.USER)
    role = "rlm_store" if product_line == "store" else f"rplm_{product_line}"
    queue = {"product_line": product_line, "region": "central", "role": role}
    return Case(
        id="GEO-STR-000001",
        reference="GEO-STR-000001",
        session_id="s1",
        status=status,
        draft=draft,
        submitted_at=T0,
        review_queue=ReviewQueue.model_validate(queue),
    )


def _steps(before: Case, name: str, after: Case | None = None) -> list[str]:
    event = WorkflowEvent(name=name, payload={})
    return [
        f"{node.value}:{outcome}" if outcome else node.value
        for node, outcome in transition_steps(before, after or before, event)
    ]


def _request(kind: str, status: str = "open") -> CaseRequest:
    return CaseRequest.model_validate(
        {
            "id": f"req_{kind}",
            "kind": kind,
            "requested_by": "r",
            "requested_at": T0,
            "status": status,
        }
    )


def _go(case: Case, name: str, **payload: Any) -> Case:
    return transition(
        case,
        WorkflowEvent(name=name, payload=payload),
        actor=CENTRAL_STORE,
        now=T0 + timedelta(minutes=1),
    )


def test_node_ids_are_the_charts() -> None:
    assert {n.value for n in N} >= {"complete1", "ref1", "approve_lead", "approve_lead2", "end"}
    assert not {n.value for n in N} & IGNORED_NODES


def test_first_level_steps() -> None:
    first = _case(CaseStatus.FIRST_REVIEW)
    assert _steps(first, "approved_first") == [
        "docsok:yes",
        "approve_pt:yes",
        "ptc_create",
        "qualified",
        "prod2:no",
    ]
    assert _steps(first, "approved_first", _case(CaseStatus.SECOND_REVIEW, "media"))[-1] == (
        "prod2:yes"
    )
    assert _steps(first, "rejected") == ["approve_pt:no", "not_q", "rej_mail"]
    assert _steps(first, "reupload_requested") == ["docsok:no", "reup_req", "reup_mail"]
    assert _steps(first, "routed") == ["vla"]


def test_second_level_steps() -> None:
    second = _case(CaseStatus.SECOND_REVIEW)
    assert _steps(second, "unit_assigned") == ["rsm"]
    assert _steps(_case(CaseStatus.SECOND_REVIEW, "media"), "unit_assigned") == ["rplm"]
    assert _steps(second, "sales_data_requested") == ["fsd_q:yes", "fsd_notify"]
    assert _steps(second, "lead_approved") == ["fsd_q:no", "approve_lead:yes"]
    assert _steps(second, "rejected") == ["fsd_q:no", "approve_lead:no", "reject_lead", "rej_mail"]
    # Once Forecasted Sales Data was asked for, "fsd_q" isn't recorded again.
    second.requests.append(_request("sales_data", "fulfilled"))
    assert _steps(second, "lead_approved") == ["approve_lead:yes"]
    assert _steps(second, "rejected")[0] == "approve_lead:no"


def test_lead_approved_steps() -> None:
    lead = _case(CaseStatus.LEAD_APPROVED)
    assert _steps(lead, "contacts_requested") == ["req_contacts", "contacts_notify"]
    assert _steps(lead, "contacts_provided") == ["contacts_provide"]
    assert _steps(lead, "approved") == ["approve_lead2", "create_all"]
    assert _steps(_case(CaseStatus.APPROVED), "sent_to_yardi") == ["yardi_box", "end"]
    # The old second level (contacts at second review) has no chart steps for these.
    assert _steps(_case(CaseStatus.SECOND_REVIEW), "contacts_provided") == []


def test_second_review_rows_follow_policy() -> None:
    second = _case(CaseStatus.SECOND_REVIEW)
    events = legal_events(second, CENTRAL_STORE)
    assert "unit_assigned" in events
    assert {"lead_approved", "approved", "contacts_requested"}.isdisjoint(events)
    with pytest.raises(IllegalTransition) as refused:
        _go(second, "approved")
    assert refused.value.code == "illegal_transition"


def test_legacy_case_keeps_the_old_rows() -> None:
    """A case whose contacts request opened at first approval (before flow v2) can finish."""
    legacy = _case(CaseStatus.SECOND_REVIEW)
    legacy.requests.append(_request("contacts"))
    events = legal_events(legacy, CENTRAL_STORE)
    assert "request_withdrawn" in events and "unit_assigned" in events
    # The old final approval is still a row (refused on its blockers, not as illegal).
    with pytest.raises(IllegalTransition) as blocked:
        _go(legacy, "approved")
    assert blocked.value.code == "invalid_payload"
    withdrawn = _go(legacy, "request_withdrawn", kind="contacts")
    assert withdrawn.status == CaseStatus.SECOND_REVIEW


def test_lead_approval_blockers() -> None:
    second = _case(CaseStatus.SECOND_REVIEW)
    assert lead_approval_blockers(second) == ["unit_not_assigned"]
    second.assigned_unit = AssignedUnit(
        mall_id="riyadh-mall-a", unit_ref="RMA-G-014", area_sqm=None, by="r", at=T0
    )
    second.requests.append(_request("sales_data"))
    assert lead_approval_blockers(second) == ["sales_data_pending"]
    with pytest.raises(IllegalTransition) as refused:
        _go(second, "lead_approved")
    assert refused.value.code == "invalid_payload"
    second.requests[0].status = "fulfilled"
    approved = _go(second, "lead_approved", remarks="Good fit")
    assert approved.status == CaseStatus.LEAD_APPROVED
    decision = approved.decisions[-1]
    assert (decision.level, decision.outcome, decision.remarks) == (
        "second",
        "lead_approved",
        "Good fit",
    )


def test_no_reject_after_approve_lead() -> None:
    lead = _case(CaseStatus.LEAD_APPROVED)
    assert "rejected" not in legal_events(lead, CENTRAL_STORE)
    with pytest.raises(IllegalTransition):
        _go(lead, "rejected", remarks="No")
