"""Cards for the intake channels (spec §15): basic-info review, the application link,
the existing-CR choice and the sign-in prompt."""

from __future__ import annotations

from app.api.cards import _mask_email
from app.api.schemas import (
    BasicInfoReviewPayload,
    BasicInfoRow,
    ExistingCrChoiceOption,
    ExistingCrChoicePayload,
    SendLinkPayload,
    SignInPromptPayload,
    UiCard,
)
from app.domain import draft_ops
from app.domain.fields import FIELD_BY_KEY, FieldGroup
from app.domain.master import MasterData
from app.domain.models import NEEDS_CONFIRMATION, FieldKey, InquiryDraft
from app.domain.rules import can_submit

BASIC_INFO_CARD_ID = "basic_info_review"
SEND_LINK_CARD_ID = "send_link"
EXISTING_CR_CARD_ID = "existing_cr_choice"
SIGN_IN_CARD_ID = "sign_in_prompt"

# Basic info: every field outside the document numbers (intake channels §3.3).
BASIC_GROUPS = (FieldGroup.COMPANY, FieldGroup.BRAND, FieldGroup.SPACE, FieldGroup.CONTACT)
BASIC_KEYS: tuple[FieldKey, ...] = tuple(
    key for key, definition in FIELD_BY_KEY.items() if definition.group in BASIC_GROUPS
)


def basic_info_missing(draft: InquiryDraft) -> list[str]:
    """Labels of required basic-info fields still empty (contact = mobile or landline)."""
    missing: list[str] = []
    for blocker in can_submit(draft):
        if not blocker.token.startswith("missing_field:"):
            continue
        key = blocker.token.split(":", 1)[1]
        if key == "contact":
            missing.append("Mobile or landline")
            continue
        definition = FIELD_BY_KEY.get(FieldKey(key))
        if definition is not None and definition.group in BASIC_GROUPS:
            missing.append(definition.label)
    return missing


def confirm_basic_info(draft: InquiryDraft) -> tuple[InquiryDraft, list[str]]:
    """Proceed: confirm every derived, verified or staff basic-info value in one step."""
    keys = [
        key.value
        for key in BASIC_KEYS
        if draft.fields[key].value not in (None, "", [])
        and draft.fields[key].source in NEEDS_CONFIRMATION
        and not draft.fields[key].confirmed
    ]
    return (draft_ops.confirm(draft, keys) if keys else draft), keys


def build_basic_info_card(
    draft: InquiryDraft,
    master: MasterData,
    *,
    started_by: str | None,
    title: str = "Please check your details",
    proceeded: bool = False,
    message_id: str | None = None,
) -> UiCard:
    rows: list[BasicInfoRow] = []
    for key in BASIC_KEYS:
        definition = FIELD_BY_KEY[key]
        field = draft.fields[key]
        display = definition.display(draft, master)
        if display in (None, "") and not definition.required:
            continue
        if field.source is not None and field.source.value == "default":
            continue
        rows.append(
            BasicInfoRow(
                key=key.value,
                label=definition.label,
                display=display,
                source=field.source.value if field.source else None,
                confirmed=field.confirmed,
                required=definition.required,
            )
        )
    missing = basic_info_missing(draft)
    payload = BasicInfoReviewPayload(
        title=title,
        started_by=started_by,
        rows=rows,
        missing=missing,
        can_proceed=not missing,
        proceeded=proceeded,
    )
    return UiCard(
        card_id=BASIC_INFO_CARD_ID,
        card_type="basic_info_review",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def build_send_link_card(draft: InquiryDraft, *, sent_to: str | None = None) -> UiCard:
    missing = basic_info_missing(draft)
    email = draft.fields[FieldKey.EMAIL].value
    payload = SendLinkPayload(
        email_masked=_mask_email(str(email)) if email else None,
        can_send=not missing and bool(email) and draft.cr_status != "unknown",
        missing=missing if draft.cr_status != "unknown" else ["CR check (or skip it)", *missing],
        sent_to_masked=_mask_email(sent_to) if sent_to else None,
    )
    return UiCard(card_id=SEND_LINK_CARD_ID, card_type="send_link", payload=payload.model_dump())


def build_existing_cr_choice_card(
    cr_number: str, company_name: str | None, *, chosen: str | None = None
) -> UiCard:
    payload = ExistingCrChoicePayload(
        cr_number=cr_number,
        company_name=company_name,
        options=[
            ExistingCrChoiceOption(value="sign_in", label="Ask them to sign in"),
            ExistingCrChoiceOption(value="continue", label="Continue for them"),
        ],
        chosen=chosen,  # type: ignore[arg-type]
    )
    return UiCard(
        card_id=EXISTING_CR_CARD_ID, card_type="existing_cr_choice", payload=payload.model_dump()
    )


def build_sign_in_prompt_card(public_base_url: str) -> UiCard:
    payload = SignInPromptPayload(
        message=(
            "This CR already has a Tenant Central account. Sign in to raise an inquiry from "
            "Leasing Opportunities, with your details already filled in."
        ),
        sign_in_url=f"{public_base_url.rstrip('/')}/tenant",
        button_label="Sign in to Tenant Central",
    )
    return UiCard(card_id=SIGN_IN_CARD_ID, card_type="sign_in_prompt", payload=payload.model_dump())
