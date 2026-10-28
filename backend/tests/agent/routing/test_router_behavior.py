"""Router behaviour beyond the labelled fixture set (PR #38 review)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.agent.redirect import stream_redirect_reply
from app.agent.router import Intent, classify_intent, route_message, set_classifier_for_tests
from app.agent.runtime import AgentRuntime
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.sessions import Session


def _session(*, reference: str | None = None, collecting: bool = False) -> Session:
    now = datetime.now(tz=UTC)
    draft = new_inquiry_draft()
    if collecting:
        draft.cr_status = "skipped"
        draft, _, _ = write_fields(
            draft,
            [(FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER)],
            master=load_master_data(),
        )
    if reference:
        draft.reference = reference
    return Session(id="sess-router-beh", draft=draft, created_at=now, last_seen=now)


def _scripted_runtime(agent_runtime: AgentRuntime) -> AgentRuntime:
    settings = agent_runtime.settings.model_copy(update={"agent_mode": "scripted"})
    return AgentRuntime(
        services=agent_runtime.services,
        master=agent_runtime.master,
        settings=settings,
    )


@pytest.mark.asyncio
async def test_scripted_mode_skips_classifier(agent_runtime: AgentRuntime) -> None:
    runtime = _scripted_runtime(agent_runtime)
    with patch("app.agent.router.classify_intent", new_callable=AsyncMock) as mock_classify:
        decision = await route_message(
            "I have a question about signage rules",
            _session(),
            runtime,
        )
        mock_classify.assert_not_called()
    assert decision.intent == Intent.INQUIRY_INTAKE
    assert decision.via == "fallback"


@pytest.mark.asyncio
async def test_scripted_redirect_does_not_call_model(agent_runtime: AgentRuntime) -> None:
    runtime = _scripted_runtime(agent_runtime)
    session = _session()
    with patch("app.agent.model.get_chat_model") as mock_factory:
        with patch.object(runtime.services.gateway, "call", new_callable=AsyncMock) as mock_gw:
            events = [
                item
                async for item in stream_redirect_reply(
                    Intent.GENERAL_INQUIRY,
                    "signage rules?",
                    session,
                    runtime,
                )
            ]
            mock_factory.assert_not_called()
            mock_gw.assert_not_called()
    assert any(e["event"] == "token" for e in events)
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_mid_intake_does_not_call_classifier(agent_runtime: AgentRuntime) -> None:
    with patch("app.agent.router.classify_intent", new_callable=AsyncMock) as mock_classify:
        decision = await route_message(
            "What documents do I need?",
            _session(collecting=True),
            agent_runtime,
        )
        mock_classify.assert_not_called()
    assert decision.intent == Intent.INQUIRY_INTAKE
    assert decision.via == "fallback"


@pytest.mark.asyncio
async def test_contact_line_with_call_me_is_not_human_help(agent_runtime: AgentRuntime) -> None:
    decision = await route_message(
        "Sara Ali, call me on 0501234567",
        _session(collecting=True),
        agent_runtime,
    )
    assert decision.intent != Intent.HUMAN_HELP


@pytest.mark.asyncio
async def test_follow_on_another_store_stays_intake(agent_runtime: AgentRuntime) -> None:
    def wrong(_text: str, _status: str):
        from app.agent.router import ClassifierResult

        return ClassifierResult(intent=Intent.EXISTING_TENANT_NEW_SPACE, confidence=0.99)

    set_classifier_for_tests(wrong)
    try:
        decision = await route_message(
            "Can we do another store at Mall of Arabia?",
            _session(reference="GEO-STR-999999"),
            agent_runtime,
        )
    finally:
        set_classifier_for_tests(None)
    assert decision.intent == Intent.INQUIRY_INTAKE


@pytest.mark.asyncio
async def test_classify_uses_llm_router_service(agent_runtime: AgentRuntime) -> None:
    settings = Settings(
        upload_dir=agent_runtime.settings.upload_dir,
        openai_api_key="sk-test",
        openai_model="gpt-test",
    )
    runtime = AgentRuntime(
        services=agent_runtime.services,
        master=agent_runtime.master,
        settings=settings,
    )

    async def fake_call(service: str, operation: str, fn, *args, inquiry_id=None, **kwargs):
        assert service == "llm_router"
        assert operation == "route_classify"
        from app.agent.router import ClassifierResult

        return ClassifierResult(intent=Intent.OFF_TOPIC, confidence=0.9)

    with patch.object(runtime.services.gateway, "call", side_effect=fake_call):
        result = await classify_intent("poem", "phase=gate", runtime=runtime, session_id="s1")
    assert result.intent == Intent.OFF_TOPIC
