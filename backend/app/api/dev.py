"""Dev and demo tools (L3 §3.4). Mounted only when DEV_TOOLS=true with mock integrations.

- `GET /api/dev/outbox?to=` / `DELETE /api/dev/outbox`: the simulated email and SMS
  outbox behind `/dev/inbox`. It may hold the mock OTP; it is never logged.
- `GET /api/dev/audit/{inquiry_id}`: the redacted audit trail of one inquiry.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

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


@router.get("/audit/{inquiry_id}")
async def get_audit(
    inquiry_id: str,
    services: ServiceContainer = Depends(get_services),
) -> dict[str, Any]:
    return {"inquiry_id": inquiry_id, "events": services.audit.events(inquiry_id)}
