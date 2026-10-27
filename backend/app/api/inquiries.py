"""Inquiry status for the private tracking page (L3 §3.4).

`GET /api/inquiries/{reference}?t=<token>` needs the signed `track` token from the
submission email or the success card: a guessable reference alone must not expose an
applicant's case. A missing, wrong or expired token gets the same 404 as an unknown
reference, with no data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_services
from app.api.deps import get_settings as get_settings_dep
from app.api.limiter import limiter
from app.api.schemas import InquiryStatusResponse, InquiryStatusStep, StepState
from app.config import Settings
from app.gateway import GatewayError
from app.security import tokens
from app.services.container import ServiceContainer
from app.services.errors import ReferenceNotFoundError
from app.services.status import STAGES

router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])

_STATUS_STEPS: list[tuple[str, str, StepState]] = [
    ("submitted", "Inquiry submitted", "done"),
    ("review", "Review", "current"),
    ("sign_in", "Sign in to Tenant Central", "upcoming"),
]


@router.get("/{reference}", response_model=InquiryStatusResponse)
@limiter.limit("60/minute")
async def get_inquiry_status(
    request: Request,
    reference: str,
    t: str | None = Query(default=None),
    services: ServiceContainer = Depends(get_services),
    settings: Settings = Depends(get_settings_dep),
) -> InquiryStatusResponse:
    try:
        claims = tokens.read(settings.token_secret, t or "", "track")
    except tokens.TokenError as exc:
        raise ReferenceNotFoundError(reference) from exc
    if claims.subject != reference:
        raise ReferenceNotFoundError(reference)
    try:
        inquiry = services.gateway.call_sync(
            "status", "get", services.status.get, reference, inquiry_id=claims.data.get("i")
        )
    except GatewayError as exc:
        raise ReferenceNotFoundError(reference) from exc

    current_index = next(i for i, (key, _l) in enumerate(STAGES) if key == inquiry.current_stage)
    stages = [
        InquiryStatusStep(
            key=key,
            label=label,
            state="done" if i < current_index else "current" if i == current_index else "upcoming",
        )
        for i, (key, label) in enumerate(STAGES)
    ]
    steps = [
        InquiryStatusStep(key=key, label=label, state=state) for key, label, state in _STATUS_STEPS
    ]
    return InquiryStatusResponse(
        reference=inquiry.reference,
        status=inquiry.status,
        submitted_at=inquiry.submitted_at,
        steps=steps,
        stages=stages,
        current_stage=inquiry.current_stage,
        owner_role=inquiry.owner_role,
        waiting_on_you=list(inquiry.waiting_on_you),
        last_change=inquiry.last_change,
    )
