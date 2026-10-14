"""Inquiry status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_services
from app.api.limiter import limiter
from app.api.schemas import InquiryStatusResponse, InquiryStatusStep, StepState
from app.services.container import ServiceContainer

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
    services: ServiceContainer = Depends(get_services),
) -> InquiryStatusResponse:
    inquiry = services.status.get(reference)
    steps = [
        InquiryStatusStep(key=key, label=label, state=state) for key, label, state in _STATUS_STEPS
    ]
    return InquiryStatusResponse(
        reference=inquiry.reference,
        status=inquiry.status,
        submitted_at=inquiry.submitted_at,
        steps=steps,
    )
