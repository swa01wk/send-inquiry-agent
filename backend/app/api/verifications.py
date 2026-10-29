"""Email verification by link (L3 §3.2).

The emailed link opens `/inquiry/verify?t=<token>` in the frontend, which calls
`POST /api/verifications/email {token}`. The token must be valid, unexpired and unused,
and the inquiry's email must still be the address the link was sent to. On success the
email is verified and the response carries a `resume_token` for "Continue your inquiry".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agent.channels import started_by_label
from app.agent.runtime import AgentRuntime
from app.api.cards import (
    VERIFICATION_CARD_ID,
    _mask_email,
    scope_card_data,
    scoped_card_id,
)
from app.api.channel_cards import build_basic_info_card
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
    complete = _complete_claims(settings, body.token)
    if complete is not None:
        return await complete_application(complete, store, services, settings)
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


# ---- The application link from the call centre (intake channels §3.3) -----------------

COMPLETE_GREETING = (
    "{started_by} started this inquiry for you with the details you gave on the phone. "
    "Please check them below and press Proceed — or edit anything that isn't right."
)


def _complete_claims(settings: Settings, token: str) -> tokens.TokenClaims | None:
    """The claims of a `complete` token; None for any other link (handled as before)."""
    try:
        return tokens.read(settings.token_secret, token, "complete")
    except tokens.TokenError as exc:
        if exc.code == "token_expired":  # purpose is checked first: it was a complete link
            raise ApiError(400, "token_expired", _MESSAGES["token_expired"]) from exc
        return None


async def complete_application(
    claims: tokens.TokenClaims,
    store: SessionStore,
    services: ServiceContainer,
    settings: Settings,
) -> VerifyEmailResponse:
    """Opening the link verifies the email and continues the inquiry in a new chat for the
    applicant, starting with the basic-info review (the staff chat stays with the staff)."""
    try:
        staff_session = await store.revive(claims.subject)
    except SessionNotFound as exc:
        raise ApiError(404, "inquiry_not_found", "We couldn't find that inquiry.") from exc
    if staff_session.complete_nonce != claims.nonce:
        raise ApiError(400, "token_used", _MESSAGES["token_used"])
    email = staff_session.draft.fields[FieldKey.EMAIL].value
    if not email or email != staff_session.link_sent_to:
        raise ApiError(400, "email_changed", _MESSAGES["email_changed"])

    draft = staff_session.draft.model_copy(deep=True)
    draft.email_verified = True
    session = await store.create(
        draft=draft,
        channel=staff_session.channel,
        created_by=staff_session.created_by,
        tenant_id=staff_session.tenant_id,
    )
    services.storage.copy_session_files(staff_session.id, session.id)  # type: ignore[attr-defined]
    staff_session.complete_nonce = None  # single use
    staff_session.closed = "handed_to_applicant"
    store.save(staff_session)

    master = load_master_data()
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    started_by = started_by_label(runtime, staff_session.created_by)
    message_id = "complete-1"
    session.add_message(message_id, "assistant", COMPLETE_GREETING.format(started_by=started_by))
    card = build_basic_info_card(
        draft, master, started_by=started_by.lower().replace("the cenomi", "the Cenomi")
    )
    card.message_id = message_id
    session.remember_card(card.model_dump())
    services.audit.record(
        session.id, "inquiry_created", actor="staff", payload={"channel": session.channel}
    )
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
        email_masked=_mask_email(str(email)),
        resume_token=issue_resume_token(settings, session.id),
    )
