"""Human handoff (L3 §3.6): a call-centre case and the handoff card.

`start_handoff` is shared by every trigger: the `request_handoff` UI action (the user
asked, or form mode's "Ask us to call you"), the router's `human_help` intent, and the
guard's second failed retry. It never needs the model, so it works in form mode too.

The case carries the inquiry so far and a short summary built from the draft (no model
call); the inquiry stays resumable. One open case per inquiry: asking again shows the
same case.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.blockers import blocker_message
from app.agent.context import message_context
from app.agent.runtime import AgentRuntime
from app.api.cards import build_handoff_card
from app.api.schemas import UiCard
from app.audit import Actor
from app.domain.models import FieldKey, InquiryDraft
from app.domain.rules import can_submit, compute_phase
from app.gateway import GatewayError
from app.services.call_centre import HANDOFF_REASONS

SUMMARY_MESSAGES = 3
SUMMARY_MESSAGE_CHARS = 160


@dataclass(frozen=True)
class HandoffResult:
    note: str  # `[ui_event] …` for the agent
    card: UiCard | None
    case_id: str | None
    created: bool


def inquiry_key(session_id: str, inquiry_seq: int = 1) -> str:
    """The id of one inquiry in a chat (a follow-on inquiry gets its own)."""
    return session_id if inquiry_seq <= 1 else f"{session_id}~{inquiry_seq}"


def short_ref(draft: InquiryDraft, session_id: str) -> str:
    """The submitted reference, or a short code for an inquiry not yet submitted."""
    if draft.reference:
        return draft.reference
    return f"INQ-{session_id.replace('-', '')[:6].upper()}"


def transcript_summary(draft: InquiryDraft, recent_user_messages: list[str]) -> str:
    """Where the applicant got to, for the executive picking up the case (no model call)."""
    lines = [f"Stage: {compute_phase(draft).value}."]
    blockers = [b for b in can_submit(draft) if b.token != "terms_not_accepted"]
    if blockers:
        lines.append("Still needed: " + " ".join(blocker_message(b) for b in blockers[:6]))
    else:
        lines.append("Everything needed is in; only the terms and Submit remain.")
    quoted = [
        " ".join(text.split())[:SUMMARY_MESSAGE_CHARS]
        for text in recent_user_messages[-SUMMARY_MESSAGES:]
        if text.strip()
    ]
    if quoted:
        lines.append("Last messages from the applicant: " + " | ".join(f'"{q}"' for q in quoted))
    return "\n".join(lines)


async def start_handoff(
    *,
    session_id: str,
    inquiry_seq: int,
    draft: InquiryDraft,
    recent_user_messages: list[str],
    reason: str,
    runtime: AgentRuntime,
    actor: Actor = "user",
    via: str = "card",
) -> HandoffResult:
    if reason not in HANDOFF_REASONS:
        reason = "user_asked"
    key = inquiry_key(session_id, inquiry_seq)
    ref = short_ref(draft, session_id)
    context = message_context(draft, runtime.master)
    first = draft.fields[FieldKey.FIRST_NAME].value
    last = draft.fields[FieldKey.LAST_NAME].value
    context["contact_name"] = " ".join(str(p) for p in (first, last) if p) or "not given yet"
    services = runtime.services
    try:
        case, created = await services.gateway.call(
            "call_centre",
            "create_case",
            services.call_centre.create_case,
            key,
            draft.model_dump(mode="json"),
            reason,
            transcript_summary(draft, recent_user_messages),
            short_ref=ref,
            context=context,
            inquiry_id=session_id,
        )
    except GatewayError as err:
        # Even with the case system down, the user still gets the phone number and hours.
        settings = runtime.settings
        card = build_handoff_card(
            phone=settings.call_centre_phone,
            email=settings.call_centre_email,
            hours=settings.call_centre_hours,
            short_ref=ref,
            case_id="",
            reason=reason,
        )
        services.audit.record(
            session_id,
            "error",
            actor="system",
            payload={
                "where": "call_centre.create_case",
                "kind": err.kind,
            },
        )
        return HandoffResult(
            note=f"[ui_event] handoff_created {reason} {err.note}",
            card=card,
            case_id=None,
            created=False,
        )
    settings = runtime.settings
    card = build_handoff_card(
        phone=settings.call_centre_phone,
        email=settings.call_centre_email,
        hours=settings.call_centre_hours,
        short_ref=ref,
        case_id=case.case_id,
        reason=case.reason,
    )
    services.audit.record(
        session_id,
        "handoff_created",
        actor=actor,
        payload={"reason": reason, "case_id": case.case_id, "created": created, "via": via},
    )
    tail = "" if created else " (repeat)"
    return HandoffResult(
        note=f"[ui_event] handoff_created {reason}{tail}",
        card=card,
        case_id=case.case_id,
        created=created,
    )
