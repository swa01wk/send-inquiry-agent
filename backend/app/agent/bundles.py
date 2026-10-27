"""Question bundles: which group of fields the agent should ask for next.

The agent condenses the form by asking for a whole group of fields in one
question. This module works out, deterministically, which group is next and
what is still missing in it, so the prompt can say "ask for X, Y and Z
together" instead of leaving the model to walk the form field by field.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.fields import FIELD_BY_KEY
from app.domain.models import FieldKey, InquiryDraft, Source
from app.domain.rules import contact_verified


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
        if field.source in (Source.DERIVED, Source.VERIFIED) and not field.confirmed:
            labels.append(_label(key))
    return labels


def next_bundle_hint(
    draft: InquiryDraft,
    cards_shown: list[str] | None = None,
) -> str:
    """One or two lines telling the agent what to ask for next, as one question."""
    del cards_shown  # verification progress now lives on the draft
    if draft.cr_status == "existing" or draft.reference:
        return "Next question: none (no more collection needed)."
    if draft.cr_status == "unknown":
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
        asks = _askable(draft, bundle)
        if asks:
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
                "mention once that they can add them."
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
    else:
        lines.append("Next: documents card, then the review card.")
    return "\n".join(lines)
