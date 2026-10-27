"""Runtime dependencies passed into the graph via RunnableConfig."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables.config import RunnableConfig

from app.api.cards import build_verification_card
from app.api.schemas import UiCard
from app.config import Settings
from app.domain.master import MasterData
from app.domain.models import InquiryDraft
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

    def verification_card(self, draft: InquiryDraft, session_id: str) -> UiCard:
        """The verification card with the demo token and resend availability."""
        resend = self.services.resend

        def iso(channel: str) -> str | None:
            ready = resend.available_at(session_id, channel)  # type: ignore[arg-type]
            return ready.isoformat() if ready else None

        return build_verification_card(
            draft,
            demo_token=self.email_demo_token(session_id),
            email_resend_at=iso("email"),
            mobile_resend_at=iso("sms"),
        )


def runtime_from_config(config: RunnableConfig | dict[str, Any]) -> AgentRuntime:
    configurable = config.get("configurable") or {}
    runtime = configurable.get("runtime")
    if runtime is None:
        msg = "AgentRuntime missing from config.configurable.runtime"
        raise RuntimeError(msg)
    return runtime  # type: ignore[no-any-return]
