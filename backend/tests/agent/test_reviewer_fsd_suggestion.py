"""Flow v2 E2 (§3.11): the reviewer assistant suggests asking for Forecasted Sales Data.

Facts and the configured rule only; it never sends the request and never changes the case."""

from __future__ import annotations

from typing import Any

import pytest
from app.agent.reviewer_tools import assess_forecasted_sales_need
from app.agent.runtime import AgentRuntime
from app.domain.models import FieldKey, Source
from app.policy.config import get_policy, use_policy
from app.workflow.forecasted_sales import assess_forecasted_sales
from app.workflow.models import Case, CaseRequest
from tests.agent.conftest import make_tool_runtime
from tests.agent.test_reviewer_tools import T0, _case_in_store, _snapshot, _state, _suggestion_cards

KNOWN_CR = "1010444444"  # tenant + Yardi company in the mock world
NEW_CR = "1010123456"  # registry only


def _set(case: Case, key: FieldKey, value: Any) -> None:
    case.draft.fields[key].value = value
    case.draft.fields[key].source = Source.USER
    case.draft.fields[key].confirmed = True


def _case(agent_runtime: AgentRuntime, *, cr: str, area_min: int | None = None) -> Case:
    case = _case_in_store(agent_runtime)
    _set(case, FieldKey.CR_NUMBER, cr)
    if area_min is not None:
        _set(case, FieldKey.AREA_MIN, area_min)
        _set(case, FieldKey.AREA_MAX, area_min + 50)
    agent_runtime.services.cases.save(case)
    return case


def _run(agent_runtime: AgentRuntime, case: Case, stream_events) -> tuple[str, list[dict]]:
    events, writer = stream_events
    state = _state(agent_runtime, case)
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = assess_forecasted_sales_need.invoke({"state": state, "runtime": runtime})
    return result.update["messages"][0].content, _suggestion_cards(events)


def test_new_company_is_suggested(agent_runtime, stream_events) -> None:
    case = _case(agent_runtime, cr=NEW_CR, area_min=40)
    before = _snapshot(case)
    text, cards = _run(agent_runtime, case, stream_events)
    assert "Company new to Cenomi: yes" in text
    assert "Area asked for: 40–90 sqm" in text
    assert "suggest asking" in text
    assert "RSM decides" in text
    assert len(cards) == 1
    payload = cards[0]["payload"]
    assert payload["kind"] == "sales_data_need"
    assert payload["action"] == "request_sales_data"
    assert "new to Cenomi" in payload["text"]
    after = agent_runtime.services.cases.get(case.id)
    assert after is not None and _snapshot(after) == before


def test_known_company_with_a_large_area_is_suggested(agent_runtime, stream_events) -> None:
    case = _case(agent_runtime, cr=KNOWN_CR, area_min=200)
    text, cards = _run(agent_runtime, case, stream_events)
    assert "Company new to Cenomi: no" in text
    assert len(cards) == 1
    assert "minimum area of 200 sqm" in cards[0]["payload"]["text"]


def test_known_company_with_a_small_area_is_not_suggested(agent_runtime, stream_events) -> None:
    case = _case(agent_runtime, cr=KNOWN_CR, area_min=60)
    text, cards = _run(agent_runtime, case, stream_events)
    assert "not needed" in text
    assert cards == []


def test_default_area_reads_as_not_given(agent_runtime) -> None:
    case = _case(agent_runtime, cr=KNOWN_CR)
    result = assess_forecasted_sales(case, agent_runtime.services)
    assert result.area_min is None
    assert not result.suggest
    assert "Area asked for: not given" in result.text()


def test_linked_yardi_company_counts_as_known(agent_runtime) -> None:
    case = _case(agent_runtime, cr=NEW_CR, area_min=40)
    case.yardi.company_id = "YC-1001"
    assert not assess_forecasted_sales(case, agent_runtime.services).suggest


def test_open_or_past_sales_data_request_is_not_suggested_again(
    agent_runtime, stream_events
) -> None:
    case = _case(agent_runtime, cr=NEW_CR, area_min=400)
    case.requests.append(
        CaseRequest(
            id="req-sales",
            kind="sales_data",
            status="open",
            requested_by="rlm_store-central",
            requested_at=T0,
        )
    )
    agent_runtime.services.cases.save(case)
    text, cards = _run(agent_runtime, case, stream_events)
    assert "already requested" in text
    assert cards == []


@pytest.mark.parametrize(
    ("rule", "cr", "area", "expected"),
    [
        ({"new_company": False, "area_min_sqm_at_least": 150}, NEW_CR, 40, False),
        ({"new_company": True, "area_min_sqm_at_least": None}, KNOWN_CR, 900, False),
        ({"new_company": False, "area_min_sqm_at_least": 100}, KNOWN_CR, 100, True),
    ],
)
def test_rule_comes_from_policy(agent_runtime, rule, cr, area, expected) -> None:
    case = _case(agent_runtime, cr=cr, area_min=area)
    policy = get_policy().with_changes(forecasted_sales={"suggest_when": rule})
    with use_policy(policy):
        assert assess_forecasted_sales(case, agent_runtime.services).suggest is expected
