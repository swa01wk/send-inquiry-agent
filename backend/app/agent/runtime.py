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

    def email_demo_token(self, session_id: str) -> str | None:
        """The live email-link token, exposed only in demo mode (EMAIL_LINK_DEMO)."""
        if not self.settings.email_link_demo:
            return None
        return self.services.email_verification.demo_token(session_id)


def runtime_from_config(config: RunnableConfig | dict[str, Any]) -> AgentRuntime:
    configurable = config.get("configurable") or {}
    runtime = configurable.get("runtime")
    if runtime is None:
        msg = "AgentRuntime missing from config.configurable.runtime"
        raise RuntimeError(msg)
    return runtime  # type: ignore[no-any-return]
