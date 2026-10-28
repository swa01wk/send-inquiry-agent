"""Email verification by link (L3 §3.2).

The emailed link opens `/inquiry/verify?t=<token>` in the frontend, which calls
`POST /api/verifications/email {token}`. The token must be valid, unexpired and unused,
and the inquiry's email must still be the address the link was sent to. On success the
email is verified and the response carries a `resume_token` for "Continue your inquiry".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agent.runtime import AgentRuntime
from app.api.cards import (
    VERIFICATION_CARD_ID,
    _mask_email,
    scope_card_data,
    scoped_card_id,
)
from app.api.deps import get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import VerifyEmailRequest, VerifyEmailResponse
from app.config import Settings, get_settings
from app.domain import draft_ops
from app.domain.master import load_master_data
from app.domain.models import FieldKey
from app.gateway import GatewayError
from app.security import tokens
from app.services.container import ServiceContainer
from app.sessions import SessionNotFound, SessionStore

router = APIRouter(prefix="/api/verifications", tags=["verifications"])

_MESSAGES = {
    "token_invalid": "This verification link isn't valid.",
    "token_expired": "This verification link has expired. Ask for a new one in the chat.",
    "token_used": "This link has already been used, or a newer link was sent.",
    "email_changed": "The email on the inquiry has changed since this link was sent.",
}


def issue_resume_token(settings: Settings, session_id: str) -> str:
    token, _claims = tokens.issue(
        settings.token_secret,
        "resume",
        session_id,
        ttl_seconds=settings.resume_ttl_days * 86400,
    )
    return token


@router.post("/email", response_model=VerifyEmailResponse)
@limiter.limit(get_settings().rate_limit_ip)
async def verify_email_link(
    request: Request,
    body: VerifyEmailRequest,
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    settings: Settings = Depends(get_settings_dep),
) -> VerifyEmailResponse:
    try:
        check = await services.gateway.call(
            "email", "verify_link", services.email_verification.verify_link, body.token
        )
    except GatewayError as err:
        code = err.note.replace(" ", "_")
        raise ApiError(503, code, "Please try the link again shortly.") from err
    if check.error is not None or check.session_id is None or check.verified_email is None:
        code = check.error or "token_invalid"
        if check.session_id:
            services.audit.record(
                check.session_id,
                "verification_result",
                actor="user",
                payload={"channel": "email", "result": code},
            )
        raise ApiError(400, code, _MESSAGES[code])
    try:
        session = await store.revive(check.session_id)
    except SessionNotFound as exc:
        raise ApiError(404, "inquiry_not_found", "We couldn't find that inquiry.") from exc

    current = session.draft.fields[FieldKey.EMAIL].value
    if current != check.verified_email:
        services.audit.record(
            session.id,
            "verification_result",
            actor="user",
            payload={"channel": "email", "result": "email_changed"},
        )
        raise ApiError(400, "email_changed", _MESSAGES["email_changed"])

    draft = session.draft.model_copy(deep=True)
    draft.email_verified = True
    draft_ops.stamp_verified(draft)
    session.draft = draft
    # Refresh the saved card so a resumed chat shows the email as verified.
    card_key = scoped_card_id(VERIFICATION_CARD_ID, session.inquiry_seq)
    previous = session.cards.get(card_key)
    runtime = AgentRuntime(services=services, master=load_master_data(), settings=settings)
    card = scope_card_data(
        runtime.verification_card(draft, session.id).model_dump(), session.inquiry_seq
    )
    if previous is not None:
        card["message_id"] = previous.get("message_id")
    session.remember_card(card)
    services.audit.record(
        session.id,
        "verification_result",
        actor="user",
        payload={"channel": "email", "result": "verified"},
    )
    store.save(session)
    return VerifyEmailResponse(
        status="verified",
        session_id=session.id,
        email_masked=_mask_email(str(current)),
        resume_token=issue_resume_token(settings, session.id),
    )
