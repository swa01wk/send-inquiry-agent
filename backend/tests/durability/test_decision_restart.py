"""Recovery (demo feedback §5, scenario class "recovery"): per-document and per-contact
decisions survive a restart, and an effect that didn't run before the restart runs once
after it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from app import clock
from app.agent.case_graph import build_case_graph
from app.agent.graph import build_assisted_graph, build_graph
from app.agent.model import ScriptedChatModel
from app.agent.reviewer_graph import build_reviewer_graph
from app.agent.runtime import AgentRuntime
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldValue, Source
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from app.workflow.effects import run_effects
from app.workflow.machine import transition
from app.workflow.models import TenantContact, WorkflowEvent
from httpx import ASGITransport, AsyncClient
from tests.lifecycle.conftest import APPLICANT, lifecycle_settings, submit_case
from tests.lifecycle.test_document_approval import (
    LEASE_ADMIN,
    approve_documents,
    decide,
    reviewed,
)

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin]


@pytest.fixture
async def durable(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, Any]]:
    settings = lifecycle_settings(tmp_path, data_dir=str(tmp_path / "data"))

    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=[{"content": "OK"}] * 50)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    application.state.assisted_graph = build_assisted_graph(model_factory=factory)
    application.state.case_graph = build_case_graph(model_factory=factory)
    application.state.reviewer_graph = build_reviewer_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, application


def _contact(role: str, email: str) -> dict[str, Any]:
    def typed(value: str) -> FieldValue:
        return FieldValue(value=value, source=Source.USER, confirmed=True)

    return TenantContact(
        role=role,  # type: ignore[arg-type]
        first_name=typed("Omar"),
        last_name=typed("Saleh"),
        email=typed(email),
        mobile=typed("+966551234567"),
    ).model_dump(mode="json")


async def test_document_decisions_survive_a_restart(durable) -> None:
    client, app = durable
    reference = await submit_case(client, app, prepare=reviewed())
    await approve_documents(client, reference)

    restarted = build_services(app.state.settings)
    case = restarted.cases.get(reference)
    assert case is not None
    decision = case.document_decisions[DocType.BRAND_PROFILE]
    assert (decision.status, decision.by) == ("approved", LEASE_ADMIN)
    assert decision.file_id == case.draft.documents[DocType.BRAND_PROFILE].file_id
    applied = [
        e["payload"]
        for e in restarted.audit.events(reference)
        if e["type"] == "case_transition" and e["payload"].get("outcome") == "applied"
    ]
    assert [p["subject"] for p in applied if p["event"] == "document_approved"] == [
        "company_profile",
        "brand_profile",
    ]


async def test_an_effect_missed_before_a_restart_runs_once_after_it(durable) -> None:
    client, app = durable
    reference = await submit_case(client, app, prepare=reviewed())
    rejected = await decide(
        client, reference, "brand_profile", "reject_document", remarks="Logo page missing"
    )
    assert rejected.status_code == 200, rejected.text
    services = app.state.services
    case = services.cases.get(reference)
    event = WorkflowEvent(name="reupload_requested", payload={})
    lease_admin = services.reviewers.get(LEASE_ADMIN).actor()
    # The transition is saved, then the process stops: no email went out.
    services.cases.save(transition(case, event, actor=lease_admin, now=clock.now()))

    restarted = build_services(app.state.settings)
    case = restarted.cases.get(reference)
    assert case.open_request("reupload") is not None

    def requests_sent() -> int:
        return len(
            [
                m
                for m in restarted.notifications.messages(to=APPLICANT)
                if m["template"] == "reupload_request"
            ]
        )

    before = requests_sent()
    rt = AgentRuntime(services=restarted, master=load_master_data(), settings=app.state.settings)
    await run_effects(rt, case, event)
    await run_effects(rt, restarted.cases.get(reference), event)  # a retry sends nothing
    assert requests_sent() == before + 1
