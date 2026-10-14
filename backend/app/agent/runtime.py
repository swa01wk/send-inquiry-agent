"""Runtime dependencies passed into the graph via RunnableConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables.config import RunnableConfig

from app.config import Settings
from app.domain.master import MasterData
from app.services.container import ServiceContainer


@dataclass(frozen=True)
class AgentRuntime:
    services: ServiceContainer
    master: MasterData
    settings: Settings


def runtime_from_config(config: RunnableConfig | dict[str, Any]) -> AgentRuntime:
    configurable = config.get("configurable") or {}
    runtime = configurable.get("runtime")
    if runtime is None:
        msg = "AgentRuntime missing from config.configurable.runtime"
        raise RuntimeError(msg)
    return runtime  # type: ignore[no-any-return]
