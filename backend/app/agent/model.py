"""Chat model factory and scripted fake for tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import Field, PrivateAttr

from app.config import Settings, get_settings

_MISSING = object()


class ModelUnavailable(Exception):
    """The chat model failed twice in one turn (L3 §3.14): the session goes to form mode."""

    def __init__(self, kind: str) -> None:
        super().__init__(f"model unavailable: {kind}")
        self.kind = kind  # "timeout" | "unavailable"


def model_error_kind(exc: BaseException) -> str | None:
    """`timeout` / `unavailable` for a failed call to the model provider; None for a bug.

    Provider and network errors (openai, httpx) mean the model is unreachable; anything
    else is our own error and must surface as one.
    """
    module = type(exc).__module__ or ""
    if not module.startswith(("openai", "httpx", "httpcore")):
        return None
    name = type(exc).__name__.lower()
    return "timeout" if "timeout" in name else "unavailable"


def supports_temperature(model: str) -> bool:
    """GPT-5 and o-series models reject non-default temperature (400 from the API)."""
    lower = model.lower()
    return not lower.startswith(("gpt-5", "o1", "o3", "o4"))


def is_reasoning_model(model: str) -> bool:
    lower = model.lower()
    return lower.startswith(("gpt-5", "o1", "o3", "o4"))


def build_chat_model(
    settings: Settings,
    *,
    model: str | None = None,
    temperature: float | None | object = _MISSING,
    streaming: bool = True,
) -> BaseChatModel:
    """Build ChatOpenAI or AzureChatOpenAI from settings."""
    cfg = settings.require_llm()
    deployment = model or cfg.model
    temp: float | None
    if temperature is _MISSING:
        temp = settings.llm_temperature
    else:
        temp = temperature  # type: ignore[assignment]

    kwargs: dict[str, Any] = {"streaming": streaming}
    if temp is not None and supports_temperature(deployment):
        kwargs["temperature"] = temp
    if settings.llm_reasoning_effort and is_reasoning_model(deployment):
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort

    if cfg.provider == "azure":
        assert cfg.endpoint is not None
        return AzureChatOpenAI(
            azure_endpoint=cfg.endpoint,
            api_key=cfg.api_key,
            api_version=cfg.api_version or settings.azure_openai_api_version,
            azure_deployment=deployment,
            model=deployment,
            **kwargs,
        )
    return ChatOpenAI(
        model=deployment,
        api_key=cfg.api_key,
        **kwargs,
    )


def get_chat_model() -> BaseChatModel:
    return build_chat_model(get_settings(), streaming=True)


class ScriptedChatModel(BaseChatModel):
    """Returns predetermined assistant messages for tests."""

    steps: list[dict[str, Any]] = Field(default_factory=list)
    _bound_tools: list[BaseTool] | None = None
    _step_index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    @property
    def streaming(self) -> bool:
        return False

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> ScriptedChatModel:
        del kwargs
        clone = self.model_copy(deep=True)
        clone._bound_tools = list(tools)  # type: ignore[arg-type]
        clone._step_index = self._step_index
        return clone

    def _next_message(self) -> AIMessage:
        index = self._step_index
        if index >= len(self.steps):
            return AIMessage(content="(no more scripted steps)")
        step = self.steps[index]
        self._step_index = index + 1
        content = step.get("content", "")
        tool_calls = step.get("tool_calls")
        if tool_calls:
            return AIMessage(content=content or "", tool_calls=tool_calls)
        return AIMessage(content=content)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del messages, stop, run_manager, kwargs
        message = self._next_message()
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
