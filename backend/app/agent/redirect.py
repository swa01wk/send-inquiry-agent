"""Short redirect replies for non-intake intents (L3 §3.5). No write tools."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.events import SseEvent
from app.agent.router import Intent
from app.agent.runtime import AgentRuntime
from app.domain.rules import compute_phase
from app.sessions import Session

_REDIRECT_SYSTEM: dict[Intent, str] = {
    Intent.GENERAL_INQUIRY: (
        "You are the Cenomi leasing assistant. The user has a general tenant question "
        "(not a new leasing inquiry). In two or three short sentences, explain that "
        "General Inquiries are raised after they sign in to Tenant Central, and offer "
        "to continue helping with a new leasing inquiry here if they like. "
        "Do not invent contact details. Match the user's language (Arabic or English)."
    ),
    Intent.EXISTING_TENANT_NEW_SPACE: (
        "You are the Cenomi leasing assistant. The user is an existing Cenomi tenant "
        "who wants additional space. In two or three short sentences, kindly point them "
        "to Sign In on Tenant Central and Leasing Opportunities to request a new unit. "
        "Offer to continue a brand-new leasing inquiry in this chat if they are not "
        "already a tenant. Match the user's language (Arabic or English)."
    ),
    Intent.OFF_TOPIC: (
        "You are the Cenomi leasing assistant. The user's message is unrelated to "
        "mall leasing. In one or two friendly sentences, say you are here to help with "
        "leasing inquiries and invite them to continue. Match the user's language."
    ),
}

_SCRIPTED_REDIRECT: dict[Intent, str] = {
    Intent.GENERAL_INQUIRY: (
        "General tenant questions are raised after you sign in to Tenant Central. "
        "I'm here if you'd like to continue a new leasing inquiry in this chat."
    ),
    Intent.EXISTING_TENANT_NEW_SPACE: (
        "If you're already a Cenomi tenant, sign in to Tenant Central and open "
        "Leasing Opportunities to request another unit. I can also help you start "
        "a brand-new leasing inquiry here."
    ),
    Intent.OFF_TOPIC: (
        "I'm here to help with mall leasing inquiries. Tell me about your brand "
        "and the space you're looking for whenever you're ready."
    ),
}

_DEFAULT_FALLBACK = (
    "I'm here to help with leasing inquiries for Cenomi malls. "
    "Tell me about your brand and the space you're looking for whenever you're ready."
)


def _chunk_text(text: str, size: int = 24) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


async def stream_redirect_reply(
    intent: Intent,
    user_text: str,
    session: Session,
    runtime: AgentRuntime,
) -> AsyncIterator[SseEvent]:
    """Stream a redirect assistant bubble (gateway service `llm_router`, no tools)."""
    system = _REDIRECT_SYSTEM.get(intent)
    if system is None:
        return

    message_id = f"m_{uuid.uuid4().hex[:10]}"

    if runtime.settings.agent_mode == "scripted":
        reply = _SCRIPTED_REDIRECT.get(intent, _DEFAULT_FALLBACK)
    else:
        reply = _DEFAULT_FALLBACK
        try:
            from app.agent.model import get_chat_model

            model = get_chat_model()
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=user_text),
            ]

            async def _invoke() -> str:
                response = await model.ainvoke(messages)
                content = response.content
                return content if isinstance(content, str) else str(content)

            reply = await runtime.services.gateway.call(
                "llm_router",
                "redirect",
                _invoke,
                inquiry_id=session.id,
            )
        except Exception:
            reply = _SCRIPTED_REDIRECT.get(intent, _DEFAULT_FALLBACK)

    for piece in _chunk_text(reply.strip()):
        yield SseEvent(event="token", data={"message_id": message_id, "text": piece})
    yield SseEvent(event="done", data={"phase": compute_phase(session.draft).value})
