"""Apply a CR registry answer to the draft (shared by the `verify_cr` tool and form mode)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from app.api.channel_cards import (
    CompanyRegistrationState,
    build_company_registration_card,
    build_sign_in_prompt_card,
    mask_cr,
)
from app.api.schemas import UiCard
from app.domain import draft_ops
from app.domain import validation as v
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey, InquiryDraft, Source
from app.gateway import GatewayError
from app.policy import get_policy
from app.services.cr import CrResult
from app.workflow.flow import FlowNode, record_flow_step

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime
    from app.sessions import Session

CrKind = Literal["existing", "new"]
CONFIRMABLE_FROM_CR = (FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value)


@dataclass
class CrOutcome:
    kind: CrKind
    draft: InquiryDraft
    changed: list[str]
    confirm_keys: list[str] = field(default_factory=list)
    errors: dict[str, v.ValidationError] = field(default_factory=dict)


def apply_cr_result(
    draft: InquiryDraft,
    cr_number: str,
    result: CrResult,
    master: MasterData,
) -> CrOutcome:
    """Existing account → `existing`: the person signs in (chart S3, M18). New → prefill the
    company name and address as `verified`, unconfirmed, for the user to confirm."""
    if result.exists:
        updated = draft.model_copy(deep=True)
        updated.cr_status = "existing"
        updated, written, _errors = draft_ops.write_fields(
            updated, [(FieldKey.CR_NUMBER.value, cr_number, Source.USER)], master=master
        )
        return CrOutcome(kind="existing", draft=updated, changed=["cr_number", *written])

    entries: list[tuple[str, object, Source]] = [
        (FieldKey.CR_NUMBER.value, cr_number, Source.USER),
    ]
    if result.company_name:
        entries.append((FieldKey.COMPANY_NAME.value, result.company_name, Source.VERIFIED))
    if result.company_address:
        entries.append((FieldKey.COMPANY_ADDRESS.value, result.company_address, Source.VERIFIED))
    updated, written, errors = draft_ops.write_fields(draft, entries, master=master)
    updated.cr_status = "new"
    confirm_keys = [k for k in written if k in CONFIRMABLE_FROM_CR]
    return CrOutcome(
        kind="new", draft=updated, changed=written, confirm_keys=confirm_keys, errors=errors
    )


# ---- Flow v2 Check for Existing Customer (spec flow-v2-alignment §3.2; day F3) ------------
#
# A deterministic handler, not a model tool (ADR-V4): the CR typed on the Company
# Registration card, or in the chat, is checked here before the graph runs; the model gets
# only the outcome note, never the number.

CR_INVALID_MESSAGE = "That doesn't look like a 10-digit CR number. Please check it and try again."
CR_SERVICE_MESSAGE = "We couldn't check the CR just now. Please try again in a moment, or skip it."
CR_CERTIFICATE_UNREADABLE = (
    "We couldn't read a CR number from that certificate. Please type the number instead, "
    "or skip it."
)


@dataclass
class CustomerCheck:
    """What the check did: the `[ui_event]` note, the Company Registration card as it now
    stands, the sign-in card for a registered CR, and the draft keys that changed."""

    note: str
    card: UiCard
    sign_in: UiCard | None = None
    changed: list[str] = field(default_factory=list)


def _certificate_name(draft: InquiryDraft) -> str | None:
    ref = draft.documents.get(DocType.CR_CERTIFICATE)
    return ref.file_name if ref is not None else None


def _offers_no_login() -> bool:
    return get_policy().registered_cr_without_login == "continue"


def certificate_customer_check(session: Session, runtime: AgentRuntime) -> CustomerCheck:
    """M1 (16 Nov): the CR certificate uploaded on the Company Registration card. The number
    the document review service read from it is checked like a typed one; it never reaches
    the model (FV9)."""
    name = _certificate_name(session.draft)
    if session.draft.cr_status != "unknown":
        return CustomerCheck(note="[ui_event] cr_already_done", card=_current_card(session.draft))
    ref = session.draft.documents.get(DocType.CR_CERTIFICATE)
    read = ref.review.fields.get(FieldKey.CR_NUMBER.value) if ref and ref.review else None
    if read is None or not isinstance(v.validate_cr_number(read.value), str):
        return CustomerCheck(
            note="[ui_event] cr_certificate_unreadable",
            card=build_company_registration_card(
                state="open", error=CR_CERTIFICATE_UNREADABLE, certificate_name=name
            ),
        )
    return check_existing_customer(session, runtime, read.value)


def check_existing_customer(session: Session, runtime: AgentRuntime, raw: str) -> CustomerCheck:
    """Verify on the Company Registration card, or a CR typed in the public chat."""
    record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.CHK_TP, actor="user")
    certificate = _certificate_name(session.draft)
    validated = v.validate_cr_number(raw)
    if isinstance(validated, v.ValidationError):
        return CustomerCheck(
            note=f"[ui_event] cr_invalid {validated.code}",
            card=build_company_registration_card(
                state="open", error=CR_INVALID_MESSAGE, certificate_name=certificate
            ),
        )
    if session.draft.cr_status != "unknown":
        return CustomerCheck(note="[ui_event] cr_already_done", card=_current_card(session.draft))
    record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.DB)
    try:
        result = runtime.services.gateway.call_sync(
            "cr", "verify", runtime.services.cr.verify, validated, inquiry_id=session.id
        )
    except GatewayError as err:
        return CustomerCheck(
            note=f"[ui_event] {err.note}",
            card=build_company_registration_card(
                state="open", error=CR_SERVICE_MESSAGE, certificate_name=certificate
            ),
        )
    masked = mask_cr(validated)
    draft, written, _errors = draft_ops.write_fields(
        session.draft, [(FieldKey.CR_NUMBER.value, validated, Source.USER)], master=runtime.master
    )
    if result.exists:
        # Registered (E1): one line and the sign-in card; nothing else is asked (M18).
        draft.cr_status = "existing"
        session.draft = draft
        session.closed = "redirected_to_sign_in"
        record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.EXIST, outcome="yes")
        record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.DISPLAY)
        record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.REDIRECT)
        runtime.services.audit.record(
            session.id,
            "inquiry_redirected",
            actor="system",
            payload={"reason": "registered_cr", "channel": session.channel},
        )
        return CustomerCheck(
            note="[ui_event] cr_checked registered"
            + (" no_login_offered" if _offers_no_login() else ""),
            card=build_company_registration_card(
                state="registered", cr_masked=masked, certificate_name=certificate
            ),
            sign_in=build_sign_in_prompt_card(
                runtime.settings.public_base_url,
                reason="registered_cr",
                offer_no_login=_offers_no_login(),
            ),
            changed=["cr_status", *written],
        )
    # Not registered (M23): the CR stays on the inquiry; the registry's company name and
    # address aren't written — Basic Info asks for them.
    draft.cr_status = "new"
    session.draft = draft
    record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.EXIST, outcome="no")
    return CustomerCheck(
        note="[ui_event] cr_checked not_registered",
        card=build_company_registration_card(
            state="not_registered", cr_masked=masked, certificate_name=certificate
        ),
        changed=["cr_status", *written],
    )


def continue_without_login(session: Session, runtime: AgentRuntime) -> CustomerCheck:
    """S4, M2 (decided 16 Nov; policy `registered_cr_without_login: continue`): "I don't have
    a login" on the sign-in card. The chat opens again and the inquiry goes on as new, with
    the CR kept and `registered_no_login` set for the Leasing Admin."""
    draft = session.draft
    if (
        not _offers_no_login()
        or draft.intake_flow != "v2"
        or draft.cr_status != "existing"
        or draft.reference
    ):
        return CustomerCheck(note="[ui_event] no_login_unavailable", card=_current_card(draft))
    updated = draft.model_copy(deep=True)
    updated.cr_status = "new"
    updated.registered_no_login = True
    session.draft = updated
    session.closed = None
    runtime.services.audit.record(
        session.id,
        "inquiry_continued_without_login",
        actor="user",
        payload={"channel": session.channel},
    )
    return CustomerCheck(
        note="[ui_event] continued_without_login",
        card=_current_card(updated),
        sign_in=build_sign_in_prompt_card(
            runtime.settings.public_base_url,
            reason="registered_cr",
            continued_without_login=True,
        ),
        changed=["cr_status"],
    )


def skip_customer_check(
    session: Session, runtime: AgentRuntime, *, confirmed: bool
) -> CustomerCheck:
    """Skip on the card: the first press asks "Are you sure you want to proceed without CR
    ID?"; only `confirmed` completes it."""
    if session.draft.cr_status != "unknown":
        return CustomerCheck(note="[ui_event] cr_already_done", card=_current_card(session.draft))
    if not confirmed:
        return CustomerCheck(
            note="[ui_event] cr_skip_confirm_shown",
            card=build_company_registration_card(state="confirm_skip"),
        )
    draft = session.draft.model_copy(deep=True)
    draft.cr_status = "skipped"
    session.draft = draft
    record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.CHK_TP, actor="user")
    record_flow_step(runtime, inquiry_id=session.id, node=FlowNode.EXIST, outcome="skipped")
    return CustomerCheck(
        note="[ui_event] cr_skipped",
        card=build_company_registration_card(state="skipped"),
        changed=["cr_status"],
    )


def _current_card(draft: InquiryDraft) -> UiCard:
    cr = draft.fields[FieldKey.CR_NUMBER].value
    masked = mask_cr(str(cr)) if cr else None
    state: CompanyRegistrationState = {
        "existing": "registered",
        "new": "not_registered",
        "skipped": "skipped",
    }.get(draft.cr_status, "open")  # type: ignore[assignment]
    if draft.registered_no_login:
        state = "continued_no_login"
    return build_company_registration_card(
        state=state, cr_masked=masked, certificate_name=_certificate_name(draft)
    )


def company_registration_card(draft: InquiryDraft, *, error: str | None = None) -> UiCard:
    """The card as the draft now stands (after a certificate upload, say)."""
    if error is None:
        return _current_card(draft)
    return build_company_registration_card(
        state="open", error=error, certificate_name=_certificate_name(draft)
    )
