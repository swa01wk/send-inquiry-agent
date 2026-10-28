"""Intent routing before the intake agent (L3 §3.5; step 21).

Rules decide first; otherwise a small structured-output classifier. Mid-intake and
low-confidence messages stay on the intake path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from app.agent.runtime import AgentRuntime
from app.domain.rules import compute_phase
from app.domain.validation import normalise_digits
from app.policy.config import get_policy
from app.sessions import Session

REFERENCE_RE = re.compile(r"\bGEO-(?:STR|MED|SPC)-\d{6}\b", re.IGNORECASE)

_HUMAN_HELP_RE = re.compile(
    r"\b("
    r"talk to (?:a |someone|somebody|a person|a human|an agent|customer service|support)|"
    r"speak to (?:a |someone|somebody|a person|a human|an agent|customer service|support)|"
    r"call me|phone call|real person|human help|"
    r"أبي (?:أتكلم|اكلم)|"
    r"أبغى (?:أتكلم|اتكلم)|"
    r"كلمني|"
    r"موظف|"
    r"خدمة العملاء"
    r")\b",
    re.IGNORECASE,
)

_EXISTING_TENANT_LANG_RE = re.compile(
    r"\b("
    r"already (?:lease|rent|have|operate)|"
    r"existing tenant|"
    r"we(?:'re| are) already a tenant|"
    r"another (?:store|shop|unit|space|location)|"
    r"third (?:store|unit|location)|"
    r"second (?:store|unit|location)|"
    r"عندنا (?:متجر|فرع|وحدة)|"
    r"مستأجر(?:ين)?|"
    r"نبي (?:متجر|وحدة|فرع) (?:ثاني|ثالث|إضافي)"
    r")\b",
    re.IGNORECASE,
)


class Intent(StrEnum):
    INQUIRY_INTAKE = "inquiry_intake"
    INQUIRY_STATUS = "inquiry_status"
    GENERAL_INQUIRY = "general_inquiry"
    EXISTING_TENANT_NEW_SPACE = "existing_tenant_new_space"
    HUMAN_HELP = "human_help"
    OFF_TOPIC = "off_topic"


class ClassifierResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)


class ClassifierProtocol(Protocol):
    def __call__(self, text: str, inquiry_status: str) -> ClassifierResult: ...


@dataclass(frozen=True)
class RouteDecision:
    intent: Intent
    via: Literal["rule", "classifier", "fallback"]
    confidence: float | None = None


def _inquiry_status_label(session: Session) -> str:
    draft = session.draft
    phase = compute_phase(draft).value
    parts = [f"phase={phase}"]
    if draft.reference:
        parts.append(f"reference={draft.reference}")
    if draft.follow_on_of:
        parts.append(f"follow_on_of={draft.follow_on_of}")
    if draft.cr_status != "unknown":
        parts.append(f"cr_status={draft.cr_status}")
    return ", ".join(parts)


def _rule_intent(text: str, session: Session) -> Intent | None:
    normalised = normalise_digits(text).strip()
    if REFERENCE_RE.search(normalised):
        return Intent.INQUIRY_STATUS
    if _HUMAN_HELP_RE.search(normalised):
        return Intent.HUMAN_HELP
    policy = get_policy()
    if policy.existing_tenant_policy == "sign_in":
        if _EXISTING_TENANT_LANG_RE.search(normalised):
            return Intent.EXISTING_TENANT_NEW_SPACE
        if session.draft.cr_status == "existing":
            return Intent.EXISTING_TENANT_NEW_SPACE
    return None


def _mid_intake(session: Session) -> bool:
    return compute_phase(session.draft) != "gate"


async def classify_intent(
    text: str,
    inquiry_status: str,
    *,
    runtime: AgentRuntime,
    session_id: str,
) -> ClassifierResult:
    """Structured-output classifier (`ROUTER_MODEL`), via the gateway as service `llm`."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    settings = runtime.settings
    model_name = settings.router_model or settings.openai_model
    api_key = settings.openai_api_key
    if not api_key or not model_name:
        return ClassifierResult(intent=Intent.INQUIRY_INTAKE, confidence=0.0)

    structured = ChatOpenAI(
        model=model_name,
        api_key=SecretStr(api_key),
        temperature=0,
    ).with_structured_output(ClassifierResult)

    system = (
        "Classify the user's message for a mall leasing inquiry chatbot. "
        "Return intent and confidence 0–1. "
        "Intents: inquiry_intake (new leasing inquiry or continuing one), "
        "inquiry_status (asking about a GEO- reference or application progress), "
        "general_inquiry (signage, policies, non-leasing tenant questions), "
        "existing_tenant_new_space (already a Cenomi tenant wanting more space), "
        "human_help (wants a person), off_topic (unrelated)."
    )
    user = f"Inquiry status: {inquiry_status}\n\nUser message:\n{text}"

    async def _invoke() -> ClassifierResult:
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        result = await structured.ainvoke(messages)
        if isinstance(result, ClassifierResult):
            return result
        return ClassifierResult.model_validate(result)

    try:
        return await runtime.services.gateway.call(
            "llm",
            "route_classify",
            _invoke,
            inquiry_id=session_id,
        )
    except Exception:
        return ClassifierResult(intent=Intent.INQUIRY_INTAKE, confidence=0.0)


_classifier_override: ClassifierProtocol | None = None


def set_classifier_for_tests(classifier: ClassifierProtocol | None) -> None:
    global _classifier_override
    _classifier_override = classifier


async def route_message(
    text: str,
    session: Session,
    runtime: AgentRuntime,
    *,
    classifier: ClassifierProtocol | None = None,
) -> RouteDecision:
    ruled = _rule_intent(text, session)
    if ruled is not None:
        return RouteDecision(intent=ruled, via="rule")

    classify = classifier or _classifier_override
    status = _inquiry_status_label(session)
    if classify is not None:
        result = classify(text, status)
    else:
        result = await classify_intent(text, status, runtime=runtime, session_id=session.id)

    min_conf = runtime.settings.router_min_confidence
    if result.confidence < min_conf or _mid_intake(session):
        return RouteDecision(
            intent=Intent.INQUIRY_INTAKE,
            via="fallback",
            confidence=result.confidence,
        )
    return RouteDecision(intent=result.intent, via="classifier", confidence=result.confidence)


def record_routing_audit(
    runtime: AgentRuntime,
    session_id: str,
    *,
    intent: Intent,
    via: str,
    confidence: float | None,
) -> None:
    payload: dict[str, Any] = {"intent": intent.value, "via": via}
    if confidence is not None:
        payload["confidence"] = round(confidence, 3)
    runtime.services.audit.record(
        session_id,
        "routing_decision",
        actor="system",
        payload=payload,
    )
