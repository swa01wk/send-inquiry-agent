"""Dev and demo tools (L3 §3.4). Mounted only when DEV_TOOLS=true with mock integrations.

- `GET /api/dev/outbox?to=` / `DELETE /api/dev/outbox`: the simulated email and SMS
  outbox behind `/dev/inbox`. It may hold the mock OTP; it is never logged.
- `GET /api/dev/audit/{inquiry_id}`: the redacted audit trail of one inquiry.
- `GET /api/dev/identity/accept/{invitation_id}`: accept a mock Azure AD invitation.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.api.deps import get_services
from app.services.container import ServiceContainer

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.get("/outbox")
async def list_outbox(
    to: str | None = Query(default=None),
    services: ServiceContainer = Depends(get_services),
) -> dict[str, list[dict[str, Any]]]:
    return {"messages": services.notifications.messages(to=to)}


@router.delete("/outbox")
async def clear_outbox(
    services: ServiceContainer = Depends(get_services),
) -> dict[str, bool]:
    services.notifications.clear()
    return {"cleared": True}


@router.get("/identity/accept/{invitation_id}", response_class=HTMLResponse)
async def accept_invitation(
    invitation_id: str,
    services: ServiceContainer = Depends(get_services),
) -> HTMLResponse:
    """The mock Azure AD invitation's "Accept invitation" link (L4 §3.2, assumption A3)."""
    invitation = services.identity.accept(invitation_id)
    if invitation is None:
        return HTMLResponse("<p>This invitation isn't valid.</p>", status_code=404)
    # Keep the case's onboarding record in step (the console and the brief show it).
    for case in services.cases.all():
        for recorded in case.onboarding.invitations:
            if recorded.id == invitation.id and recorded.accepted_at is None:
                recorded.accepted_at = invitation.accepted_at
                services.cases.save(case)
    return HTMLResponse(
        "<!doctype html><title>Invitation accepted</title>"
        "<p>Invitation accepted. Your Tenant Central account is ready (simulated Azure AD).</p>"
    )


@router.get("/audit/{inquiry_id}")
async def get_audit(
    inquiry_id: str,
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    return {"inquiry_id": inquiry_id, "events": services.audit.events(inquiry_id)}
