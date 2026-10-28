"""Chat model factory and scripted fake for tests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import Field, PrivateAttr, SecretStr

from app.config import get_settings


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


def get_chat_model() -> ChatOpenAI:
    settings = get_settings()
    api_key, model = settings.require_openai()
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(api_key),
        temperature=settings.openai_temperature,
        streaming=True,
    )


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
