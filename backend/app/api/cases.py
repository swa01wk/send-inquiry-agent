"""Open a case in chat from a link after submission (L4 §3.5, §3.9).

`POST /api/cases/open {token}` takes a `case` token (a request link from an email) or a
`track` token (the tracking link). It reopens the case's chat session in case mode (or
starts one, seeded with the inquiry as submitted) and returns it like
`POST /api/sessions`, with a `case_status` card and the card for each open request.
Nothing is reachable with a reference alone.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.agent.runtime import AgentRuntime
from app.api.case_cards import build_case_status_card, request_cards
from app.api.deps import get_master_data, get_services, get_session_store
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.api.limiter import limiter
from app.api.schemas import CreateSessionResponse, ResumeRequest
from app.api.sessions import resume_payload
from app.config import Settings, get_settings
from app.domain.master import MasterData
from app.security import tokens
from app.services.container import ServiceContainer
from app.sessions import Session, SessionNotFound, SessionStore
from app.workflow.models import Case, TenantContact

router = APIRouter(prefix="/api/cases", tags=["cases"])

OPEN_MESSAGE = "Here's where your inquiry {reference} stands."
WELCOME_BACK = "Welcome back. Here's the latest on {reference}."


def _read(settings: Settings, token: str) -> str:
    """The reference a `case` or `track` token is for."""
    purposes: tuple[tokens.Purpose, ...] = ("case", "track")
    for purpose in purposes:
        try:
            claims = tokens.read(settings.token_secret, token, purpose)
        except tokens.TokenError as exc:
            if exc.code == "token_expired":
                raise ApiError(
                    400, "token_expired", "This link has expired. Use your tracking link."
                ) from exc
            continue
        return claims.subject
    raise ApiError(400, "token_invalid", "This link isn't valid.")


async def _case_session(store: SessionStore, case: Case) -> tuple[Session, bool]:
    if case.case_session_id:
        try:
            return await store.revive(case.case_session_id), False
        except SessionNotFound:
            pass
    session = await store.create(
        draft=case.draft.model_copy(deep=True), mode="case", case_id=case.id
    )
    session.contacts_draft = [c.model_dump(mode="json") for c in case.tenant_contacts]
    return session, True


@router.post("/open", response_model=CreateSessionResponse)
@limiter.limit(get_settings().rate_limit_ip)
async def open_case(
    request: Request,
    body: ResumeRequest,
    store: SessionStore = Depends(get_session_store),
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> CreateSessionResponse:
    reference = _read(settings, body.token)
    case = services.cases.get(reference)
    if case is None:
        raise ApiError(404, "inquiry_not_found", "We couldn't find that inquiry.")
    session, created = await _case_session(store, case)
    if created:
        case.case_session_id = session.id
        services.cases.save(case)
        services.audit.record(
            session.id, "inquiry_created", actor="user", payload={"channel": "case_link"}
        )
    message_id = f"case-{len(session.transcript) + 1}"
    text = (OPEN_MESSAGE if created else WELCOME_BACK).format(reference=case.reference)
    session.add_message(message_id, "assistant", text)
    runtime = AgentRuntime(services=services, master=master, settings=settings)
    contacts = [TenantContact.model_validate(c) for c in session.contacts_draft]
    cards = [
        build_case_status_card(case, message_id=message_id),
        *request_cards(
            case, session.draft, runtime.master, max_mb=settings.max_upload_mb, contacts=contacts
        ),
    ]
    for card in cards:
        card.message_id = message_id
        session.remember_card(card.model_dump())
    store.save(session)
    return resume_payload(session, master)
