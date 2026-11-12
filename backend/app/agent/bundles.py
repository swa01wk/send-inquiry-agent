"""Question bundles: which group of fields the agent should ask for next.

The agent condenses the form by asking for a whole group of fields in one
question. This module works out, deterministically, which group is next and
what is still missing in it, so the prompt can say "ask for X, Y and Z
together" instead of leaving the model to walk the form field by field.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.api.channel_cards import basic_info_missing
from app.domain.fields import FIELD_BY_KEY
from app.domain.models import NEEDS_CONFIRMATION, DocType, FieldKey, InquiryDraft, Source
from app.domain.rules import contact_verified, open_fields, remaining_steps
from app.domain.sections import (
    SECTION_LABELS,
    SECTION_ORDER,
    IntakeSection,
    current_section,
    missing_in,
    section_done,
    section_rank,
)
from app.policy.config import get_policy


@dataclass(frozen=True)
class Bundle:
    name: str
    required: tuple[FieldKey, ...]
    optional: tuple[FieldKey, ...] = ()


COMPANY = Bundle("company", (FieldKey.COMPANY_NAME, FieldKey.COMPANY_ADDRESS))
BRAND_AND_SPACE = Bundle(
    "brand and space",
    (
        FieldKey.BRAND_NAME_EN,
        FieldKey.BRAND_NAME_AR,
        FieldKey.UNIT_TYPE,
        FieldKey.SALES_CATEGORY,
        FieldKey.MALLS,
    ),
    (FieldKey.AREA_MIN, FieldKey.RENT_MAX, FieldKey.LEASE_PERIOD),
)
CONTACT = Bundle("contact", (FieldKey.FIRST_NAME, FieldKey.LAST_NAME, FieldKey.EMAIL))

# Fields the agent can infer itself; they should not appear in a question.
_INFERRED = {FieldKey.BRAND_NAME_AR, FieldKey.UNIT_TYPE, FieldKey.SALES_CATEGORY}


def _has_value(draft: InquiryDraft, key: FieldKey) -> bool:
    value = draft.fields[key].value
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, list) and not value:
        return False
    return True


def _has_contact_number(draft: InquiryDraft) -> bool:
    return _has_value(draft, FieldKey.MOBILE) or _has_value(draft, FieldKey.LANDLINE)


def _label(key: FieldKey) -> str:
    return FIELD_BY_KEY[key].label


def _missing(draft: InquiryDraft, bundle: Bundle) -> list[str]:
    missing = [_label(k) for k in bundle.required if not _has_value(draft, k)]
    if bundle is CONTACT and not _has_contact_number(draft):
        missing.append("Phone number")
    return missing


def _askable(draft: InquiryDraft, bundle: Bundle) -> list[str]:
    """Missing fields the user has to tell us (excludes what we can infer)."""
    asks = [_label(k) for k in bundle.required if k not in _INFERRED and not _has_value(draft, k)]
    if bundle is BRAND_AND_SPACE and not _has_value(draft, FieldKey.UNIT_TYPE):
        asks.append("what they sell and the kind of space (kiosk, shop, media)")
    if bundle is CONTACT and not _has_contact_number(draft):
        asks.append("Phone number")
    return asks


def _arabic_name_to_ask(draft: InquiryDraft) -> bool:
    """The Brand Profile filled the brand and the Arabic name is still missing: ask for it,
    don't infer it (system prompt: "Ask for the Arabic name only when the Brand Profile
    filled the brand"). Re-demo flow 3, 10 Nov: the hint said "infer the remaining
    values", the opposite, and the agent asked for neither."""
    if _has_value(draft, FieldKey.BRAND_NAME_AR):
        return False
    profile = draft.documents.get(DocType.BRAND_PROFILE)
    return profile is not None and FieldKey.BRAND_NAME_EN.value in profile.filled_fields


def _verification_sent(draft: InquiryDraft) -> bool:
    """A link (and code, when a mobile was given) went to the current addresses."""
    email = draft.fields[FieldKey.EMAIL].value
    mobile = draft.fields[FieldKey.MOBILE].value
    email_ok = draft.email_verified or (
        email is not None and draft.email_link_sent_to == str(email)
    )
    mobile_ok = mobile is None or draft.mobile_verified or draft.otp_sent_to == str(mobile)
    return email_ok and mobile_ok


def _unconfirmed(draft: InquiryDraft, *, exclude_keys: frozenset[str] = frozenset()) -> list[str]:
    labels: list[str] = []
    for key, field in draft.fields.items():
        if key.value in exclude_keys:
            continue
        if not _has_value(draft, key):
            continue
        if field.source in NEEDS_CONFIRMATION and not field.confirmed:
            labels.append(_label(key))
    return labels


def next_bundle_hint(
    draft: InquiryDraft,
    cards_shown: list[str] | None = None,
    *,
    assisted: bool = False,
    tenant_brands: list[str] | None = None,
) -> str:
    """One or two lines telling the agent what to ask for next, as one question."""
    del cards_shown  # verification progress now lives on the draft
    if draft.cr_status == "existing" or draft.reference:
        return "Next question: none (no more collection needed)."
    if draft.intake_flow == "v2" and not assisted:
        return _v2_hint(draft)
    if draft.cr_status == "unknown":
        if not assisted and get_policy().public_cr_check == "ask_then_sign_in":
            # Demo feedback §3.1. Self-service and existing-tenant chats reach here with
            # cr_status unknown only on the public page (tenants start as "tenant").
            return (
                "Next question: ask whether the company has a CR, pointing to the card's "
                "buttons. Never ask for the CR number. If the user volunteers other details, "
                "save them too."
            )
        return (
            "Next question: ask for the CR number (or offer to continue without it). "
            "If the user volunteers other details, save them too."
        )

    lines: list[str] = []
    pending = _unconfirmed(draft, exclude_keys=frozenset())
    if pending:
        lines.append(
            "Shown but not yet accepted: "
            + ", ".join(pending)
            + ". If the user carries on without objecting, confirm them this turn. "
            "If they express doubt or hesitation about a specific value "
            '(e.g. "not sure about the category"), do not confirm that field.'
        )

    for bundle in (COMPANY, BRAND_AND_SPACE, CONTACT):
        if not _missing(draft, bundle):
            continue
        if (
            bundle is BRAND_AND_SPACE
            and tenant_brands
            and not _has_value(draft, FieldKey.BRAND_NAME_EN)
        ):
            brands_or = " or ".join(tenant_brands)
            lines.append(
                "Next question (brand): ask what the new brand is — they can type it or upload "
                "its Brand Profile for you to fill in. One question. If it matches one they "
                f"already have ({brands_or}), ask once whether it's that brand or a new one. The "
                "mall and space type are already set from the unit they chose."
            )
        elif bundle is BRAND_AND_SPACE and _arabic_name_to_ask(draft):
            lines.append(
                "Next question (brand): ask for the brand name in Arabic, in chat (no card "
                "holds it). The Brand Profile gave the English name and doesn't give the "
                "Arabic one, so don't propose one. One question."
            )
        elif asks := _askable(draft, bundle):
            lines.append(
                f"Next question ({bundle.name}): ask for {', '.join(asks)} together, "
                "in one natural question."
            )
        else:
            lines.append(
                f"Next ({bundle.name}): infer the remaining values "
                f"({', '.join(_missing(draft, bundle))}) and show them for confirmation."
            )
        if bundle is BRAND_AND_SPACE:
            lines.append(
                "Size, budget and lease are optional: keep defaults unless offered; "
                "mention once that they can add them. If the user gave one and "
                "update_draft rejected it, say which value didn't fit and ask for it once; "
                "never drop it silently."
            )
            ar_field = draft.fields[FieldKey.BRAND_NAME_AR]
            if (
                ar_field.source == Source.USER
                and _has_value(draft, FieldKey.BRAND_NAME_AR)
                and not _has_value(draft, FieldKey.BRAND_NAME_EN)
            ):
                lines.append(
                    "User gave the Arabic brand only: propose a Latin spelling in your reply "
                    "and save it with update_draft (source derived) for confirmation."
                )
        return "\n".join(lines)

    if assisted:
        if not basic_info_missing(draft):
            lines.append(
                "Next: call show_application_link; the executive sends the link. "
                "Don't mention verification, codes, documents or the terms."
            )
        return "\n".join(lines)

    if not contact_verified(draft):
        if _verification_sent(draft):
            lines.append(
                "Verification already sent; wait for the user to click the email link "
                "and, if they gave a mobile, enter the SMS code in the card. "
                "Only resend if they ask."
            )
        else:
            lines.append(
                "Next: start verification (send_verification): an email link, plus an SMS "
                "code if they gave a mobile."
            )
    lines.append(still_needed_line(draft))
    return "\n".join(lines)


_STILL_NEEDED_LABELS: dict[str, str] = {
    "verify_email": "the email link (verification card)",
    "verify_mobile": "the SMS code (verification card)",
    "documents": "the required documents (documents card; request_documents if it isn't showing)",
    "terms": "the terms and Submit (review card, once everything else is done)",
}


def _field_labels(keys: list[str]) -> str:
    return ", ".join(
        "Mobile or landline" if key == "contact" else _label(FieldKey(key)) for key in keys
    )


def _fields_left(draft: InquiryDraft) -> list[str]:
    """The `fields` step named field by field (re-demo flow 3, 10 Nov: a missing Arabic
    brand name wasn't listed, so the hint said only the terms were left)."""
    missing, unconfirmed = open_fields(draft)
    parts: list[str] = []
    if missing:
        parts.append(f"{_field_labels(missing)} (ask in chat)")
    if unconfirmed:
        parts.append(f"confirming {_field_labels(unconfirmed)} (on the card that shows it)")
    return parts


def still_needed_line(draft: InquiryDraft) -> str:
    """What's left before submit, from `can_submit`; the user may do it in any order.
    Flow v2 (§3.3): the current section only."""
    if draft.intake_flow == "v2":
        return _v2_still_needed(draft)
    steps = [
        step for step in remaining_steps(draft) if step in _STILL_NEEDED_LABELS or step == "fields"
    ]
    if not steps:
        return "Still needed before submit: nothing."
    if steps == ["terms"]:
        return (
            "Still needed before submit: only the terms. Call show_review if the review card "
            "isn't showing; the user ticks the box and presses Submit there."
        )
    parts: list[str] = []
    for step in steps:
        parts.extend(_fields_left(draft) if step == "fields" else [_STILL_NEEDED_LABELS[step]])
    left = "; ".join(parts)
    return (
        f"Still needed before submit (any order): {left}. Don't call anything the last step "
        "or point to Submit while more than the terms is left. If the user asks what's next "
        "or for the submit button, name what's left and point to that card."
    )


# ---- Flow v2 public intake (spec flow-v2-alignment §3.3; day F3) ------------------------


def _v2_labels(keys: list[str]) -> str:
    return ", ".join(
        "a mobile or office landline" if key == "contact" else _label(FieldKey(key)) for key in keys
    )


def _v2_section_ask(draft: InquiryDraft, section: IntakeSection) -> str:
    max_malls = get_policy().max_malls_per_inquiry
    if section is IntakeSection.COMPANY_REGISTRATION:
        return (
            "Company Registration: ask them to enter the CR number on the Company "
            "Registration card and press Verify, or press Skip. Never repeat a CR number."
        )
    if section is IntakeSection.UNIT_AND_CATEGORY:
        asks: list[str] = []
        if not _has_value(draft, FieldKey.UNIT_TYPE):
            lines = get_policy().product_lines
            asks.append(f"the Unit Type ({' or '.join(lines)}; offer them as quick replies)")
        if not _has_value(draft, FieldKey.SALES_CATEGORY):
            asks.append(
                "what they sell (map it to a Sales Category and show it for confirmation; "
                "never set it from the brand name alone)"
            )
        if not asks:
            return "Unit Type and Sales Category: confirm the values shown on the card."
        return f"Unit Type and Sales Category: ask for {' and '.join(asks)}."
    if section is IntakeSection.BASIC_INFO:
        missing = [
            k for k in missing_in(draft, section) if k == "contact" or not _is_unconfirmed(draft, k)
        ]
        line = "Basic Info: "
        line += (
            f"ask for {_v2_labels(missing)} in one natural question"
            if missing
            else "confirm the values shown on the card"
        )
        if FieldKey.BRAND_NAME_AR.value in missing and _has_value(draft, FieldKey.BRAND_NAME_EN):
            line += "; propose the Arabic brand name and ask them to confirm it"
        return line + ". Then the verification card."
    if section is IntakeSection.VERIFICATION:
        if _verification_sent(draft):
            return (
                "Verification: already sent; wait for the email link and, with a mobile, the "
                "SMS code on the card. Only resend if they ask."
            )
        return (
            "Verification: call send_verification (email link, plus an SMS code with a "
            "mobile) and point to the card."
        )
    if section is IntakeSection.PROPERTY_DETAILS:
        malls = "a mall" if max_malls == 1 else f"one or more malls (up to {max_malls})"
        return (
            f"Property Details: ask for {malls}; the lease period, area and rent are "
            "optional — mention once that they can add them. Never mention units or unit "
            "numbers."
        )
    if section is IntakeSection.TERMS:
        return "Terms: point to the terms card; they tick it to accept."
    if section is IntakeSection.DOCUMENTS:
        return (
            "Documents: the Company Profile and Brand Profile on the documents card "
            "(request_documents if it isn't showing)."
        )
    return "Review: call show_review if the review card isn't showing; they press Submit there."


def _is_unconfirmed(draft: InquiryDraft, key: str) -> bool:
    field = draft.fields[FieldKey(key)]
    return (
        _has_value(draft, FieldKey(key))
        and field.source in NEEDS_CONFIRMATION
        and not (field.confirmed)
    )


def _v2_hint(draft: InquiryDraft) -> str:
    """One section at a time, in the app's order: the current section's ask, what's shown
    but not yet accepted, and the sections still to come (not to be asked yet)."""
    section = current_section(draft)
    lines = [f"Next question — {_v2_section_ask(draft, section)}"]
    pending = _unconfirmed(draft)
    if pending:
        lines.append(
            "Shown but not yet accepted: "
            + ", ".join(pending)
            + ". If the user carries on without objecting, confirm them this turn. "
            "If they express doubt about a specific value, do not confirm that field."
        )
    lines.append(still_needed_line(draft))
    return "\n".join(lines)


def _v2_still_needed(draft: InquiryDraft) -> str:
    section = current_section(draft)
    later = [
        SECTION_LABELS[s]
        for s in SECTION_ORDER
        if section_rank(s) > section_rank(section)
        and s is not IntakeSection.REVIEW
        and not section_done(draft, s)
    ]
    now = SECTION_LABELS[section]
    if section is IntakeSection.REVIEW:
        return "Still needed before submit: only the review card's Submit."
    tail = f" Later, in order: {', '.join(later)} — don't ask about those yet." if later else ""
    return (
        f"Current section: {now}. Ask only about this section; save anything the user "
        f"gives early and never ask it again.{tail}"
    )
