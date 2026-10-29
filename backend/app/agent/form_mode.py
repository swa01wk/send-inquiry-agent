"""Form mode: finish the inquiry when the model is unavailable (L3 §3.14, framework L1).

Every rule already lives in code and every input has a card, so nothing here needs the
model. When the model fails twice in one turn (or `FORM_MODE=true`), the session enters
form mode:
- a `form_mode` card says the assistant isn't available, lists what's still missing as
  a short form (edited with the existing `edit_field` action), offers the CR check with
  skip, and offers **Ask us to call you** (`request_handoff`);
- UI actions apply their change and emit their cards, but no agent turn runs; the phase
  (`compute_phase`) decides which card comes next: CR, details and confirmations, the
  mall picker, verification, documents, review;
- nothing is derived: the user types everything (`source=user`); values derived earlier
  still need confirming on their card;
- the next typed message tries the model again; if it answers, the chat carries on and
  the card says the assistant is back. Nothing entered in form mode is lost.
"""

from __future__ import annotations

from app.agent.runtime import AgentRuntime
from app.agent.verification import send_contact_verification
from app.api.cards import (
    VERIFICATION_CARD_ID,
    build_confirm_fields_card,
    build_document_upload_card,
    build_review_card,
)
from app.api.schemas import (
    FormModeField,
    FormModePayload,
    FormModeStep,
    MallPickerCity,
    MallPickerMall,
    MallPickerPayload,
    UiCard,
)
from app.domain.fields import FIELD_BY_KEY, FieldGroup
from app.domain.master import MasterData
from app.domain.models import NEEDS_CONFIRMATION, FieldKey, InquiryDraft, Phase
from app.domain.rules import compute_phase, contact_verified
from app.policy.config import get_policy
from app.sessions import Session

FORM_MODE_CARD_ID = "form_mode"
FORM_CONFIRM_CARD_ID = "confirm-form"
MALL_PICKER_CARD_ID = "malls"

# The fixed bubble the form-mode card sits under (no model wrote it).
FORM_MODE_NOTICE = (
    "Our assistant isn't available right now. You can finish your inquiry here, "
    "or ask us to call you."
)
_STEP_MESSAGES: dict[FormModeStep, str] = {
    "existing_account": (
        "This CR number already has a Tenant Central account. Please sign in to Tenant "
        "Central to raise a leasing request."
    ),
    "cr": "Start with your company's CR number, or skip it for now.",
    "details": "Fill in what's still missing below, and confirm anything we suggested.",
    "verification": "Verify your contact: open the link we emailed you and enter the SMS code.",
    "documents": "Upload the Company Profile and the Brand Profile.",
    "review": "Check the review card, accept the terms and submit.",
    "submitted": "Your inquiry has been sent. You'll find the reference above.",
}
BACK_MESSAGE = "Our assistant is back. Carry on in the chat, or keep using the cards."

_SELECT_KINDS: dict[FieldKey, str] = {
    FieldKey.UNIT_TYPE: "unit_types",
    FieldKey.SALES_CATEGORY: "sales_categories",
}
# Asked through their own card or row, not as plain inputs in the form.
_NOT_IN_FORM = {FieldKey.MALLS, FieldKey.MOBILE, FieldKey.LANDLINE, FieldKey.CR_NUMBER}


def _has_value(draft: InquiryDraft, key: FieldKey) -> bool:
    value = draft.fields[key].value
    return not (value is None or value == "" or value == [])


def form_step(draft: InquiryDraft) -> FormModeStep:
    phase = compute_phase(draft)
    steps: dict[Phase, FormModeStep] = {
        Phase.EXISTING_ACCOUNT: "existing_account",
        Phase.GATE: "cr",
        Phase.COLLECTING: "details",
        Phase.VERIFYING: "verification",
        Phase.DOCUMENTS: "documents",
        Phase.REVIEW: "review",
        Phase.SUBMITTED: "submitted",
    }
    return steps[phase]


def missing_fields(draft: InquiryDraft) -> list[FormModeField]:
    """Required values still empty, in panel order, as form inputs."""
    rows: list[FormModeField] = []
    for definition in FIELD_BY_KEY.values():
        key = definition.key
        if definition.group == FieldGroup.DOCUMENTS or key in _NOT_IN_FORM:
            continue
        if not definition.required or _has_value(draft, key):
            continue
        rows.append(
            FormModeField(
                key=key.value,
                label=definition.label,
                kind="select" if key in _SELECT_KINDS else "text",
                master_kind=_SELECT_KINDS.get(key),
            )
        )
    if not (_has_value(draft, FieldKey.MOBILE) or _has_value(draft, FieldKey.LANDLINE)):
        rows.append(FormModeField(key="contact_number", label="Mobile or landline", kind="text"))
    return rows


def unconfirmed_keys(draft: InquiryDraft) -> list[str]:
    return [
        key.value
        for key, field in draft.fields.items()
        if _has_value(draft, key) and field.source in NEEDS_CONFIRMATION and not field.confirmed
    ]


def build_form_mode_card(draft: InquiryDraft, *, active: bool = True) -> UiCard:
    step = form_step(draft)
    payload = FormModePayload(
        active=active,
        message=_STEP_MESSAGES[step] if active else BACK_MESSAGE,
        next_step=step,
        fields=missing_fields(draft) if active and step == "details" else [],
        can_skip_cr=step == "cr",
    )
    return UiCard(card_id=FORM_MODE_CARD_ID, card_type="form_mode", payload=payload.model_dump())


def _all_malls_picker(draft: InquiryDraft, master: MasterData) -> UiCard:
    """Every mall in one picker: in form mode no one is there to ask which city."""
    selected_raw = draft.fields[FieldKey.MALLS].value
    selected = list(selected_raw) if isinstance(selected_raw, list) else []
    max_malls = get_policy().max_malls_per_inquiry
    malls = [
        MallPickerMall(id=m.id, name=f"{m.name} ({master.label_for('cities', m.city) or m.city})")
        for m in master.malls
    ]
    payload = MallPickerPayload(
        city=MallPickerCity(id="all", label="All malls"),
        malls=malls,
        selected=selected[:max_malls],
        min_select=1,
        max_select=max_malls,
    )
    return UiCard(
        card_id=MALL_PICKER_CARD_ID, card_type="mall_picker", payload=payload.model_dump()
    )


async def form_mode_cards(session: Session, runtime: AgentRuntime) -> list[UiCard]:
    """The form-mode card, then the card(s) for the next step. May send the verification."""
    draft = session.draft
    step = form_step(draft)
    cards: list[UiCard] = []

    if step == "details":
        keys = unconfirmed_keys(draft)
        if keys:
            cards.append(
                build_confirm_fields_card(
                    draft,
                    runtime.master,
                    keys,
                    card_id=FORM_CONFIRM_CARD_ID,
                    title="Please confirm these details",
                )
            )
        if not _has_value(draft, FieldKey.MALLS):
            cards.append(_all_malls_picker(draft, runtime.master))
    elif step == "verification":
        if not contact_verified(draft):
            outcome = await send_contact_verification(
                runtime.services, runtime.master, session.id, draft, actor="system"
            )
            session.draft = draft = outcome.draft
        cards.append(runtime.verification_card(draft, session.id))
        session.cards_shown.add(VERIFICATION_CARD_ID)
    elif step == "documents":
        cards.append(
            build_document_upload_card(draft, runtime.master, max_mb=runtime.settings.max_upload_mb)
        )
        session.cards_shown.add("documents")
    elif step == "review":
        cards.append(build_review_card(draft, runtime.master))
        session.cards_shown.add("review")

    return [build_form_mode_card(draft), *cards]
