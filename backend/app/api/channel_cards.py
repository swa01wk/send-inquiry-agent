"""Cards for the intake channels (spec §15): basic-info review, the application link,
the existing-CR choice and the sign-in prompt."""

from __future__ import annotations

from typing import Literal

from app.api.cards import _mask_email
from app.api.schemas import (
    BasicInfoReviewPayload,
    BasicInfoRow,
    CompanyRegistrationPayload,
    CrQuestionPayload,
    ExistingCrChoiceOption,
    ExistingCrChoicePayload,
    SendLinkPayload,
    SignInPromptPayload,
    SkipConfirm,
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
CR_QUESTION_CARD_ID = "cr_question"

CR_QUESTION_PROMPT = "Does your company have a CR (commercial registration)?"
# The tenant portal's sign-in; once signed in it opens Leasing Opportunities, where the
# inquiry is raised (demo feedback I3).
SIGN_IN_PATH = "/tenant"

# Basic info: every field outside the document numbers (intake channels §3.3).
BASIC_GROUPS = (FieldGroup.COMPANY, FieldGroup.BRAND, FieldGroup.SPACE, FieldGroup.CONTACT)
BASIC_KEYS: tuple[FieldKey, ...] = tuple(
    key for key, definition in FIELD_BY_KEY.items() if definition.group in BASIC_GROUPS
)


# A signed-in tenant's inquiry is for a new brand (demo feedback §3.8, R4): the basic-info
# card covers the company and contact from Cenomi's records; the brand is asked for in the
# chat (typed or from the Brand Profile) and confirmed on its own card.
NEW_BRAND_KEYS: frozenset[FieldKey] = frozenset(
    {FieldKey.BRAND_NAME_EN, FieldKey.BRAND_NAME_AR, FieldKey.SALES_CATEGORY}
)


def _card_keys(new_brand: bool) -> tuple[FieldKey, ...]:
    return tuple(k for k in BASIC_KEYS if not (new_brand and k in NEW_BRAND_KEYS))


def basic_info_missing(draft: InquiryDraft, *, new_brand: bool = False) -> list[str]:
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
        if new_brand and FieldKey(key) in NEW_BRAND_KEYS:
            continue
        if definition is not None and definition.group in BASIC_GROUPS:
            missing.append(definition.label)
    return missing


def confirm_basic_info(
    draft: InquiryDraft, *, new_brand: bool = False
) -> tuple[InquiryDraft, list[str]]:
    """Proceed: confirm every derived, verified or staff basic-info value in one step."""
    keys = [
        key.value
        for key in _card_keys(new_brand)
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
    new_brand: bool = False,
) -> UiCard:
    rows: list[BasicInfoRow] = []
    for key in _card_keys(new_brand):
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
    missing = basic_info_missing(draft, new_brand=new_brand)
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


def build_sign_in_prompt_card(public_base_url: str, *, reason: str = "existing_cr") -> UiCard:
    """Sign in to Tenant Central, landing on Leasing Opportunities to raise the inquiry
    there (demo feedback §3.1, F2). `reason`: `existing_cr` (a CR lookup found an
    account) or `has_cr` (the applicant answered Yes to "Do you have a CR?")."""
    if reason == "has_cr":
        message = (
            "If your company already has a Tenant Central account, the quickest way is to "
            "sign in and raise your inquiry from Leasing Opportunities. Your company "
            "details are already on file there."
        )
    elif reason == "registered_cr":
        # Flow v2 (§3.2, E1): the chart's Display Message, word for word.
        message = "Customer already registered. Please login"
    else:
        message = (
            "This CR already has a Tenant Central account. Sign in to raise an inquiry from "
            "Leasing Opportunities, with your details already filled in."
        )
    payload = SignInPromptPayload(
        message=message,
        sign_in_url=f"{public_base_url.rstrip('/')}{SIGN_IN_PATH}",
        button_label="Sign in to Tenant Central",
    )
    return UiCard(card_id=SIGN_IN_CARD_ID, card_type="sign_in_prompt", payload=payload.model_dump())


COMPANY_REGISTRATION_CARD_ID = "company_registration"
COMPANY_REGISTRATION_PROMPT = (
    "Company Registration: enter your 10-digit CR number to check whether your company is "
    "already registered with us, or skip it."
)
SKIP_CONFIRM_PROMPT = "Are you sure you want to proceed without CR ID?"
CompanyRegistrationState = Literal[
    "open", "confirm_skip", "registered", "not_registered", "skipped"
]


def mask_cr(cr_number: str) -> str:
    """A CR shown back on the card (I8): the last four digits only."""
    return f"•••••• {cr_number[-4:]}" if len(cr_number) >= 4 else "••••"


def build_company_registration_card(
    *,
    state: CompanyRegistrationState = "open",
    cr_masked: str | None = None,
    error: str | None = None,
    message_id: str | None = None,
) -> UiCard:
    """Flow v2 Check for Existing Customer (§3.2): Verify or Skip, one card updated in
    place. The CR is never in the payload in full."""
    payload = CompanyRegistrationPayload(
        prompt=COMPANY_REGISTRATION_PROMPT,
        input_placeholder="10-digit CR number",
        verify_label="Verify",
        skip_label="Skip",
        skip_confirm=SkipConfirm(
            prompt=SKIP_CONFIRM_PROMPT,
            yes_label="Yes, continue without it",
            no_label="No, I'll enter it",
        ),
        state=state,
        cr_masked=cr_masked,
        error=error,
    )
    return UiCard(
        card_id=COMPANY_REGISTRATION_CARD_ID,
        card_type="company_registration",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def build_cr_question_card(
    *, answered: Literal["yes", "no"] | None = None, message_id: str | None = None
) -> UiCard:
    """ "Do you have a CR?" with two buttons (demo feedback §3.1). The public page never
    asks for the number itself."""
    payload = CrQuestionPayload(
        prompt=CR_QUESTION_PROMPT,
        yes_label="Yes, we have a CR",
        no_label="No, we don't",
        answered=answered,
    )
    return UiCard(
        card_id=CR_QUESTION_CARD_ID,
        card_type="cr_question",
        message_id=message_id,
        payload=payload.model_dump(),
    )
