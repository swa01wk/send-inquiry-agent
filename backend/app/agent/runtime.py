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
    # The inquiry repository, for actions that look across inquiries (flow v2
    # `resume_pending`); None where no store is wired (unit tests, evals).
    repo: Any = None
    # The chat's language ("en" | "ar", `Session.lang`): labels on `choice` cards.
    lang: str = "en"

    def verification_card(self, draft: InquiryDraft, session_id: str) -> UiCard:
        """The verification card with resend availability (no link: 18 Nov B1, N7)."""
        resend = self.services.resend

        def iso(channel: str) -> str | None:
            ready = resend.available_at(session_id, channel)  # type: ignore[arg-type]
            return ready.isoformat() if ready else None

        return build_verification_card(
            draft,
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
