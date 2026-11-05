"""Unit tests for LLM settings resolution and chat model factory (no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.agent.model import (
    build_chat_model,
    model_error_kind,
    supports_temperature,
)
from app.agent.router import classify_intent
from app.agent.runtime import AgentRuntime
from app.config import Settings
from langchain_openai import AzureChatOpenAI, ChatOpenAI

_LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_TEMPERATURE",
    "LLM_REASONING_EFFORT",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_TEMPERATURE",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
)


@pytest.fixture
def isolated_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _LLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_supports_temperature_gpt5_family() -> None:
    assert supports_temperature("gpt-4o-mini") is True
    assert supports_temperature("gpt-5.4-mini") is False
    assert supports_temperature("o1-preview") is False
    assert supports_temperature("o3-mini") is False
    assert supports_temperature("o4-mini") is False


def test_provider_resolution_endpoint_implies_azure(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        azure_openai_endpoint="https://example.cognitiveservices.azure.com/",
        azure_openai_api_key="azure-key",
        llm_model="gpt-5.4-mini",
    )
    assert settings.llm_provider == "azure"


def test_provider_resolution_llm_provider_openai_wins(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="openai",
        azure_openai_endpoint="https://example.cognitiveservices.azure.com/",
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
    )
    assert settings.llm_provider == "openai"


def test_llm_model_wins_over_openai_model(
    isolated_llm_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "from-openai")
    monkeypatch.setenv("LLM_MODEL", "from-llm")
    settings = Settings(upload_dir="./.uploads", openai_api_key="sk-test")
    assert settings.llm_model == "from-llm"


def test_openai_model_constructor_alias(isolated_llm_env: None) -> None:
    settings = Settings(upload_dir="./.uploads", openai_model="from-init", openai_api_key="sk")
    assert settings.llm_model == "from-init"
    assert settings.openai_model == "from-init"


def test_require_llm_openai_missing_key(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        openai_api_key=None,
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        settings.require_llm()


def test_require_llm_openai_missing_model(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="openai",
        openai_api_key="sk-test",
        llm_model=None,
    )
    with pytest.raises(RuntimeError, match="LLM_MODEL or OPENAI_MODEL"):
        settings.require_llm()


def test_require_llm_azure_missing_endpoint(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="azure",
        azure_openai_api_key="key",
        llm_model="deploy",
        azure_openai_endpoint=None,
    )
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        settings.require_llm()


def test_require_llm_azure_missing_key(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="azure",
        azure_openai_endpoint="https://example.cognitiveservices.azure.com/",
        llm_model="deploy",
        azure_openai_api_key=None,
    )
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        settings.require_llm()


def test_factory_openai_chat_model(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        llm_temperature=0.5,
    )
    model = build_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert model.temperature == 0.5


def test_factory_azure_no_temperature_for_gpt5_deployment(isolated_llm_env: None) -> None:
    settings = Settings(
        upload_dir="./.uploads",
        llm_provider="azure",
        azure_openai_endpoint="https://example.cognitiveservices.azure.com/",
        azure_openai_api_key="azure-key",
        azure_openai_api_version="2025-04-01-preview",
        llm_model="gpt-5.4-mini",
        llm_temperature=0.6,
    )
    model = build_chat_model(settings)
    assert isinstance(model, AzureChatOpenAI)
    assert model.deployment_name == "gpt-5.4-mini"
    assert str(model.azure_endpoint).rstrip("/") == "https://example.cognitiveservices.azure.com"
    assert model.openai_api_version == "2025-04-01-preview"
    assert "temperature" not in model.model_kwargs


def test_model_error_kind_openai_timeout() -> None:
    class APITimeoutError(Exception):
        __module__ = "openai._exceptions"

    assert model_error_kind(APITimeoutError()) == "timeout"


@pytest.mark.asyncio
async def test_router_builds_classifier_through_factory(
    agent_runtime: AgentRuntime, isolated_llm_env: None
) -> None:
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

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured

    async def fake_call(_service, _operation, fn, *args, inquiry_id=None, **kwargs):
        del args, inquiry_id, kwargs
        from app.agent.router import ClassifierResult, Intent

        mock_structured.ainvoke = AsyncMock(
            return_value=ClassifierResult(intent=Intent.OFF_TOPIC, confidence=0.9),
        )
        return await fn()

    with patch("app.agent.router.build_chat_model", return_value=mock_model) as factory:
        with patch.object(runtime.services.gateway, "call", side_effect=fake_call):
            from app.agent.router import Intent

            result = await classify_intent("poem", "phase=gate", runtime=runtime, session_id="s1")
    factory.assert_called_once()
    assert factory.call_args.args[0] is settings
    assert factory.call_args.kwargs["temperature"] == 0
    assert factory.call_args.kwargs["streaming"] is False
    assert result.intent == Intent.OFF_TOPIC
