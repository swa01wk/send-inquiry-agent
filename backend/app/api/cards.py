"""Build UiCard payloads from draft state and master data."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from app.api.schemas import (
    ConfirmFieldRow,
    ConfirmFieldsPayload,
    DocumentNumberRow,
    DocumentUploadPayload,
    MallPickerCity,
    MallPickerMall,
    MallPickerPayload,
    QuickRepliesPayload,
    QuickReplyOption,
    ReviewGroup,
    ReviewGroupRow,
    ReviewPayload,
    SuccessPayload,
    SuccessStep,
    UiCard,
    VerificationEmail,
    VerificationMobile,
    VerificationPayload,
)
from app.domain.fields import FIELD_BY_KEY, GROUP_ORDER, FieldGroup
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey, InquiryDraft
from app.domain.rules import can_submit, contact_verified
from app.domain.summary import build_draft_summary
from app.domain.validation import ALLOWED_EXTENSIONS
from app.sessions import Session

WELCOME_MESSAGE_1 = "Marhaba, and welcome to Cenomi Tenant Central! I'm your leasing assistant."
WELCOME_MESSAGE_2 = (
    "I'll help you send a leasing inquiry in a few minutes, no long form. "
    "To start, do you have your company's CR number? "
    "I'll check whether you already have an account with us."
)

WELCOME_QUICK_REPLIES: list[tuple[str, str, str | None, str | None]] = [
    (
        "I have my CR number",
        "I have my CR number",
        "focus_input",
        "Type your 10-digit CR number",
    ),
    ("I don't have it handy", "I don't have it handy", None, None),
    ("What do I need to get started?", "What do I need to get started?", None, None),
]


def dotted_allowed_extensions() -> list[str]:
    return sorted(f".{ext}" for ext in ALLOWED_EXTENSIONS)


GROUP_TITLES: dict[FieldGroup, str] = {
    FieldGroup.COMPANY: "Company",
    FieldGroup.BRAND: "Brand",
    FieldGroup.SPACE: "Space",
    FieldGroup.CONTACT: "Contact",
    FieldGroup.DOCUMENTS: "Documents",
}

SPACE_SKIP_IN_REVIEW = {
    FieldKey.AREA_MIN,
    FieldKey.AREA_MAX,
    FieldKey.RENT_MIN,
    FieldKey.RENT_MAX,
    FieldKey.RENT_PERIOD,
    FieldKey.LEASE_PERIOD,
}


def _mask_mobile(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return value
    if digits.startswith("966"):
        return f"+966{digits[-9:-4]}****{digits[-4:]}"
    return f"{value[:4]}****{value[-2:]}"


def _mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return None
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _document_number_rows(
    draft: InquiryDraft,
    *,
    number_errors: dict[str, str] | None = None,
) -> list[DocumentNumberRow]:
    rows: list[DocumentNumberRow] = []
    errors = number_errors or {}
    for key in (
        FieldKey.CR_NUMBER,
        FieldKey.VAT_NUMBER,
        FieldKey.NATIONAL_ID_NUMBER,
        FieldKey.NATIONAL_ADDRESS,
    ):
        definition = FIELD_BY_KEY[key]
        field = draft.fields[key]
        value = field.value
        display = str(value) if value not in (None, "") else None
        rows.append(
            DocumentNumberRow(
                key=key.value,
                label=definition.label,
                value=display,
                editable=key != FieldKey.CR_NUMBER,
                error=errors.get(key.value),
            ),
        )
    return rows


def document_upload_payload(
    draft: InquiryDraft,
    master: MasterData,
    *,
    max_mb: int,
    number_errors: dict[str, str] | None = None,
) -> DocumentUploadPayload:
    summary = build_draft_summary(draft, master)
    return DocumentUploadPayload(
        docs=summary.documents,
        numbers=_document_number_rows(draft, number_errors=number_errors),
        required_uploaded=summary.checks.required_docs_uploaded,
        required_total=summary.checks.required_docs_total,
        allowed_extensions=dotted_allowed_extensions(),
        max_mb=max_mb,
    )


def build_document_upload_card(
    draft: InquiryDraft,
    master: MasterData,
    *,
    max_mb: int,
    message_id: str | None = None,
    number_errors: dict[str, str] | None = None,
) -> UiCard:
    payload = document_upload_payload(
        draft,
        master,
        max_mb=max_mb,
        number_errors=number_errors,
    )
    return UiCard(
        card_id="documents",
        card_type="document_upload",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def _chip_action(action: str | None) -> Literal["send", "focus_input"]:
    if action == "focus_input":
        return "focus_input"
    return "send"


def build_quick_replies_card(
    options: list[tuple[str, str, str | None, str | None]],
    *,
    message_id: str | None = None,
) -> UiCard:
    payload = QuickRepliesPayload(
        options=[
            QuickReplyOption(
                label=label,
                text=text,
                action=_chip_action(action),
                placeholder=placeholder,
            )
            for label, text, action, placeholder in options
        ]
    )
    return UiCard(
        card_id="quick-replies",
        card_type="quick_replies",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def build_welcome_quick_replies_card(*, message_id: str) -> UiCard:
    return build_quick_replies_card(WELCOME_QUICK_REPLIES, message_id=message_id)


def next_confirm_card_id(session: Session) -> str:
    session.card_counter += 1
    return f"confirm-{session.card_counter}"


def allocate_confirm_card_id(cards_shown: list[str]) -> str:
    count = sum(1 for card_id in cards_shown if card_id.startswith("confirm-"))
    return f"confirm-{count + 1}"


def last_confirm_card_id(cards_shown: list[str]) -> str | None:
    confirm_ids = [card_id for card_id in cards_shown if card_id.startswith("confirm-")]
    return confirm_ids[-1] if confirm_ids else None


def confirm_card_id_for_keys(
    cards_shown: list[str],
    confirm_card_keys: dict[str, list[str]],
    keys: list[str],
) -> str | None:
    wanted = set(keys)
    for card_id in reversed(cards_shown):
        if not card_id.startswith("confirm-"):
            continue
        listed = confirm_card_keys.get(card_id, [])
        if wanted.intersection(listed):
            return card_id
    return None


def remember_confirm_card_keys(session: Session, card: UiCard) -> None:
    """Track which draft keys each confirm card showed (for confirm_card UI action)."""
    if card.card_type != "confirm_fields":
        return
    fields = card.payload.get("fields") or []
    keys: list[str] = []
    for row in fields:
        if isinstance(row, dict):
            key = row.get("key")
            if isinstance(key, str):
                keys.append(key)
    session.confirm_card_keys[card.card_id] = keys
    session.confirm_card_turns[card.card_id] = session.turn_index


def build_confirm_fields_card(
    draft: InquiryDraft,
    master: MasterData,
    keys: list[str],
    *,
    card_id: str,
    message_id: str | None = None,
    title: str = "Please confirm these details",
) -> UiCard:
    rows: list[ConfirmFieldRow] = []
    for key_str in keys:
        try:
            key = FieldKey(key_str)
        except ValueError:
            continue
        definition = FIELD_BY_KEY.get(key)
        if definition is None:
            continue
        field = draft.fields[key]
        rows.append(
            ConfirmFieldRow(
                key=key_str,
                label=definition.label,
                display=definition.display(draft, master),
                source=field.source.value if field.source else None,
                confirmed=field.confirmed,
            )
        )
    all_confirmed = all(row.confirmed for row in rows) if rows else True
    payload = ConfirmFieldsPayload(title=title, fields=rows, all_confirmed=all_confirmed)
    return UiCard(
        card_id=card_id,
        card_type="confirm_fields",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def build_mall_picker_card(
    draft: InquiryDraft,
    master: MasterData,
    city_id: str,
    *,
    message_id: str | None = None,
) -> UiCard:
    city_label = master.label_for("cities", city_id) or city_id
    malls = master.malls_in_city(city_id)
    selected_raw = draft.fields[FieldKey.MALLS].value
    selected = list(selected_raw) if isinstance(selected_raw, list) else []
    payload = MallPickerPayload(
        city=MallPickerCity(id=city_id, label=city_label),
        malls=[MallPickerMall(id=m.id, name=m.name) for m in malls],
        selected=selected[:1],
        min_select=1,
        max_select=1,
    )
    return UiCard(
        card_id="malls",
        card_type="mall_picker",
        message_id=message_id,
        payload=payload.model_dump(),
    )


VERIFICATION_CARD_ID = "verification"


def build_verification_card(
    draft: InquiryDraft,
    *,
    demo_token: str | None = None,
    message_id: str | None = None,
) -> UiCard:
    """Email link status plus, when a mobile was given, the mobile OTP box."""
    email = draft.fields[FieldKey.EMAIL].value
    mobile = draft.fields[FieldKey.MOBILE].value
    email_text = str(email) if email else None
    mobile_text = str(mobile) if mobile else None
    email_section = VerificationEmail(
        masked=_mask_email(email_text),
        link_sent=draft.email_link_sent_to is not None and draft.email_link_sent_to == email_text,
        verified=draft.email_verified,
        demo_token=None if draft.email_verified else demo_token,
    )
    mobile_section = (
        VerificationMobile(
            masked=_mask_mobile(mobile_text),
            code_sent=draft.otp_sent_to is not None and draft.otp_sent_to == mobile_text,
            verified=draft.mobile_verified,
            attempts_left=draft.otp_attempts_left,
        )
        if mobile_text
        else None
    )
    payload = VerificationPayload(
        email=email_section,
        mobile=mobile_section,
        all_verified=contact_verified(draft),
    )
    return UiCard(
        card_id=VERIFICATION_CARD_ID,
        card_type="verification",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def _review_composite_row(
    draft: InquiryDraft,
    master: MasterData,
    *,
    key: str,
    label: str,
    display_fn: Callable[[InquiryDraft, MasterData], str | None],
    keys: list[FieldKey],
    required: bool,
) -> ReviewGroupRow:
    source_values: list[str] = []
    for field_key in keys:
        src = draft.fields[field_key].source
        if src is not None:
            source_values.append(src.value)
    source = source_values[0] if source_values else None
    display = display_fn(draft, master)
    confirmed = all(
        draft.fields[field_key].confirmed
        for field_key in keys
        if draft.fields[field_key].value is not None
    )
    if display is None:
        confirmed = True
        source = None
    return ReviewGroupRow(
        key=key,
        label=label,
        display=display,
        source=source,
        confirmed=confirmed,
        required=required,
    )


def build_review_card(
    draft: InquiryDraft,
    master: MasterData,
    *,
    message_id: str | None = None,
) -> UiCard:
    from app.domain.fields import display_area, display_lease, display_rent

    groups: list[ReviewGroup] = []
    for group in GROUP_ORDER:
        if group == FieldGroup.DOCUMENTS:
            continue
        rows: list[ReviewGroupRow] = []
        for definition in FIELD_BY_KEY.values():
            if definition.group != group:
                continue
            if definition.key in SPACE_SKIP_IN_REVIEW:
                continue
            field = draft.fields[definition.key]
            rows.append(
                ReviewGroupRow(
                    key=definition.key.value,
                    label=definition.label,
                    display=definition.display(draft, master),
                    source=field.source.value if field.source else None,
                    confirmed=field.confirmed,
                    required=definition.required,
                )
            )
        if group == FieldGroup.SPACE:
            rows.append(
                _review_composite_row(
                    draft,
                    master,
                    key="area",
                    label="Area",
                    display_fn=lambda d, _m: display_area(d),
                    keys=[FieldKey.AREA_MIN, FieldKey.AREA_MAX],
                    required=False,
                )
            )
            rows.append(
                _review_composite_row(
                    draft,
                    master,
                    key="rent",
                    label="Rent",
                    display_fn=display_rent,
                    keys=[FieldKey.RENT_MIN, FieldKey.RENT_MAX, FieldKey.RENT_PERIOD],
                    required=False,
                )
            )
            rows.append(
                _review_composite_row(
                    draft,
                    master,
                    key="lease",
                    label="Lease period",
                    display_fn=display_lease,
                    keys=[FieldKey.LEASE_PERIOD],
                    required=False,
                )
            )
        groups.append(ReviewGroup(title=GROUP_TITLES[group], rows=rows))

    summary = build_draft_summary(draft, master)
    blockers = [b.token for b in can_submit(draft)]
    payload = ReviewPayload(
        groups=groups,
        documents=summary.documents,
        checks=summary.checks,
        can_submit=summary.can_submit,
        terms_accepted=draft.terms_accepted,
        blockers=blockers,
    )
    return UiCard(
        card_id="review",
        card_type="review",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def build_success_card(
    reference: str,
    *,
    message_id: str | None = None,
    tracking_url: str | None = None,
) -> UiCard:
    url = tracking_url or f"/api/inquiries/{reference}"
    payload = SuccessPayload(
        reference=reference,
        tracking_url=url,
        steps=[
            SuccessStep(
                label="Inquiry submitted",
                detail="Just now",
                state="done",
            ),
            SuccessStep(
                label="Review",
                detail="Our team verifies your details and documents.",
                state="current",
            ),
            SuccessStep(
                label="Sign in to Tenant Central",
                detail="After approval, with the email you registered.",
                state="upcoming",
            ),
        ],
    )
    return UiCard(
        card_id="success",
        card_type="success",
        message_id=message_id,
        payload=payload.model_dump(),
    )


def parse_doc_type(raw: str) -> DocType | None:
    try:
        return DocType(raw.strip())
    except ValueError:
        return None
