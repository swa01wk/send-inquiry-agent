"""Dev and demo tools (L3 §3.4). Mounted only when DEV_TOOLS=true with mock integrations.

- `GET /api/dev/outbox?to=` / `DELETE /api/dev/outbox`: the simulated email and SMS
  outbox behind `/dev/inbox`. It may hold the mock OTP; it is never logged.
- `GET /api/dev/audit/{inquiry_id}`: the redacted audit trail of one inquiry.
- `GET /api/dev/identity/accept/{invitation_id}`: accept a mock Azure AD invitation.
- `GET /api/dev/clock`, `POST /api/dev/clock/advance {hours}`, `POST /api/dev/clock/to-morning`:
  the simulated clock (L5 §3.1); moving it runs a proactive tick.
- `POST /api/dev/proactive/tick`: evaluate the triggers now.
- `POST /api/dev/reset`: start the demo clean (sessions, cases, outbox, invitations, Yardi
  leads, audit, attention items, uploads, clock).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agent.runtime import AgentRuntime
from app.api.deps import get_master_data, get_services
from app.api.deps import get_settings as get_settings_dep
from app.api.errors import ApiError
from app.clock import SimulatedClock
from app.config import Settings
from app.domain.master import MasterData
from app.policy.config import get_policy
from app.proactive.engine import TickResult, tick
from app.proactive.notification_policy import quiet_hours_end
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


class ClockOut(BaseModel):
    now: datetime
    offset_hours: float
    simulated: bool
    timezone: str


class AdvanceBody(BaseModel):
    hours: float = Field(gt=0, le=24 * 30)


class TickOut(BaseModel):
    clock: ClockOut
    raised: int
    sent: int
    resolved: int


def _clock_out(services: ServiceContainer) -> ClockOut:
    clock = services.clock
    offset = clock.offset if isinstance(clock, SimulatedClock) else timedelta(0)
    return ClockOut(
        now=clock.now(),
        offset_hours=round(offset.total_seconds() / 3600, 2),
        simulated=isinstance(clock, SimulatedClock),
        timezone=get_policy().proactive.quiet_hours.timezone,
    )


def _simulated(services: ServiceContainer) -> SimulatedClock:
    if not isinstance(services.clock, SimulatedClock):
        raise ApiError(409, "clock_not_simulated", "The clock is real time here.")
    return services.clock


async def _tick(services: ServiceContainer, master: MasterData, settings: Settings) -> TickOut:
    result: TickResult = await tick(
        AgentRuntime(services=services, master=master, settings=settings)
    )
    return TickOut(
        clock=_clock_out(services),
        raised=len(result.raised),
        sent=len(result.sent),
        resolved=len(result.resolved),
    )


@router.get("/clock", response_model=ClockOut)
async def get_clock(services: ServiceContainer = Depends(get_services)) -> ClockOut:
    return _clock_out(services)


@router.post("/clock/advance", response_model=TickOut)
async def advance_clock(
    body: AdvanceBody,
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    """Move simulated time forward, then run a proactive tick ("three days later")."""
    _simulated(services).advance(timedelta(hours=body.hours))
    return await _tick(services, master, settings)


@router.post("/clock/to-morning", response_model=TickOut)
async def clock_to_morning(
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    """Move to the end of the next quiet-hours window (08:00 in Riyadh by default)."""
    clock = _simulated(services)
    now = clock.now()
    clock.advance(quiet_hours_end(now, get_policy().proactive) - now)
    return await _tick(services, master, settings)


@router.post("/proactive/tick", response_model=TickOut)
async def run_tick(
    services: ServiceContainer = Depends(get_services),
    master: MasterData = Depends(get_master_data),
    settings: Settings = Depends(get_settings_dep),
) -> TickOut:
    return await _tick(services, master, settings)


@router.post("/reset")
async def reset_demo(request: Request) -> dict[str, bool]:
    """Delete every demo record and start from the mock world as shipped."""
    await request.app.state.reset_demo()
    return {"reset": True}
