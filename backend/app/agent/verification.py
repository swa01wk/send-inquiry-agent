"""Send the contact verification: the email link, and the SMS code when a mobile is given.

Shared by the `send_verification` tool and form mode (L3 §3.14), which verifies the
contact without the model. Resend limits and the gateway apply the same way to both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.context import message_context
from app.audit import Actor
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft
from app.gateway import GatewayError
from app.services.container import ServiceContainer


@dataclass
class VerificationSend:
    draft: InquiryDraft
    sent: list[str] = field(default_factory=list)  # "email verification link", "mobile code"
    throttled: list[int] = field(default_factory=list)  # seconds to wait, per channel
    failures: list[str] = field(default_factory=list)  # `service_error <service> <kind>`


async def send_contact_verification(
    services: ServiceContainer,
    master: MasterData,
    session_id: str,
    draft: InquiryDraft,
    *,
    resend: bool = False,
    actor: Actor = "agent",
) -> VerificationSend:
    """Send what isn't sent yet (or everything again with `resend`), within the limits.

    Returns the updated draft; the caller decides how to tell the user. Needs the email
    and a contact number (callers check first).
    """
    audit = services.audit
    context = message_context(draft, master)
    updated = draft.model_copy(deep=True)
    result = VerificationSend(draft=updated)
    email = draft.fields[FieldKey.EMAIL].value
    mobile = draft.fields[FieldKey.MOBILE].value

    email_text = str(email) if email else ""
    if (
        email_text
        and not updated.email_verified
        and (resend or updated.email_link_sent_to != email_text)
    ):
        is_resend = updated.email_link_sent_to == email_text
        wait = services.resend.wait_seconds(session_id, "email") if is_resend else 0
        if wait:
            result.throttled.append(wait)
            audit.record(
                session_id,
                "verification_sent",
                actor=actor,
                payload={"channel": "email", "result": "throttled"},
            )
        else:
            try:
                await services.gateway.call(
                    "email",
                    "send_link",
                    services.email_verification.send_link,
                    session_id,
                    email_text,
                    context,
                    inquiry_id=session_id,
                )
            except GatewayError as err:
                result.failures.append(err.note)
                audit.record(
                    session_id,
                    "verification_sent",
                    actor=actor,
                    payload={"channel": "email", "result": err.kind},
                )
            else:
                services.resend.record(session_id, "email")
                updated.email_link_sent_to = email_text
                result.sent.append("email verification link")
                audit.record(
                    session_id,
                    "verification_sent",
                    actor=actor,
                    payload={"channel": "email", "result": "sent"},
                )

    mobile_text = str(mobile) if mobile else None
    if (
        mobile_text
        and not updated.mobile_verified
        and (resend or updated.otp_sent_to != mobile_text)
    ):
        is_resend = updated.otp_sent_to == mobile_text
        wait = services.resend.wait_seconds(session_id, "sms") if is_resend else 0
        if wait:
            result.throttled.append(wait)
            audit.record(
                session_id,
                "verification_sent",
                actor=actor,
                payload={"channel": "sms", "result": "throttled"},
            )
        else:
            try:
                await services.gateway.call(
                    "otp",
                    "send",
                    services.otp.send,
                    session_id,
                    mobile_text,
                    context,
                    inquiry_id=session_id,
                )
            except GatewayError as err:
                result.failures.append(err.note)
                audit.record(
                    session_id,
                    "verification_sent",
                    actor=actor,
                    payload={"channel": "sms", "result": err.kind},
                )
            else:
                services.resend.record(session_id, "sms")
                updated.otp_sent_to = mobile_text
                updated.otp_attempts_left = 3
                result.sent.append("mobile code")
                audit.record(
                    session_id,
                    "verification_sent",
                    actor=actor,
                    payload={"channel": "sms", "result": "sent"},
                )
    return result
