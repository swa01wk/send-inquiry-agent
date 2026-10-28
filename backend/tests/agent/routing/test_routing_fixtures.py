"""Routing accuracy on labelled fixtures (breadth: ≥ 90% with a scripted classifier)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.agent.router import ClassifierResult, Intent, route_message, set_classifier_for_tests
from app.agent.runtime import AgentRuntime
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey
from app.sessions import Session

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures.jsonl"


def _load_fixtures() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in FIXTURES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _session_for_phase(phase_hint: str) -> Session:
    now = datetime.now(tz=UTC)
    draft = new_inquiry_draft()
    if phase_hint == "collecting":
        draft.fields[FieldKey.BRAND_NAME_EN].value = "Bean Street"
        draft.fields[FieldKey.BRAND_NAME_EN].confirmed = True
    elif phase_hint == "verifying":
        draft.fields[FieldKey.EMAIL].value = "a@example.com"
        draft.fields[FieldKey.EMAIL].confirmed = True
    elif phase_hint == "documents":
        draft.fields[FieldKey.EMAIL].value = "a@example.com"
        draft.fields[FieldKey.MOBILE].value = "+966501234567"
        draft.email_verified = True
        draft.mobile_verified = True
    elif phase_hint == "review":
        draft.fields[FieldKey.COMPANY_NAME].value = "Acme"
        draft.fields[FieldKey.COMPANY_NAME].confirmed = True
    elif phase_hint == "submitted":
        draft.reference = "GEO-STR-111111"
    return Session(id="sess-routing-test", draft=draft, created_at=now, last_seen=now)


@pytest.fixture
def routing_runtime(agent_runtime: AgentRuntime) -> AgentRuntime:
    return agent_runtime


@pytest.mark.asyncio
async def test_routing_fixtures_at_least_ninety_percent(routing_runtime: AgentRuntime) -> None:
    fixtures = _load_fixtures()
    assert len(fixtures) >= 30

    by_text = {row["text"]: row["intent"] for row in fixtures}

    def oracle(text: str, _status: str) -> ClassifierResult:
        label = by_text.get(text, "inquiry_intake")
        return ClassifierResult(intent=Intent(label), confidence=0.95)

    set_classifier_for_tests(oracle)
    try:
        correct = 0
        for row in fixtures:
            session = _session_for_phase(row.get("phase", "gate"))
            decision = await route_message(row["text"], session, routing_runtime)
            if decision.intent.value == row["intent"]:
                correct += 1
        accuracy = correct / len(fixtures)
        assert accuracy >= 0.9, f"routing accuracy {accuracy:.1%} on {len(fixtures)} fixtures"
    finally:
        set_classifier_for_tests(None)


@pytest.mark.asyncio
async def test_rules_override_classifier(routing_runtime: AgentRuntime) -> None:
    def wrong(_text: str, _status: str) -> ClassifierResult:
        return ClassifierResult(intent=Intent.OFF_TOPIC, confidence=0.99)

    set_classifier_for_tests(wrong)
    try:
        session = _session_for_phase("gate")
        decision = await route_message("Can I talk to someone?", session, routing_runtime)
        assert decision.intent == Intent.HUMAN_HELP
        assert decision.via == "rule"
    finally:
        set_classifier_for_tests(None)
