"""Submit rules and phase computation."""

from __future__ import annotations

from typing import Literal

from app.domain.fields import FIELD_BY_KEY, FieldGroup, document_definitions
from app.domain.models import NEEDS_CONFIRMATION, Blocker, FieldKey, InquiryDraft, Phase


def _has_value(draft: InquiryDraft, key: FieldKey) -> bool:
    val = draft.fields[key].value
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    if isinstance(val, list) and len(val) == 0:
        return False
    return True


def _contact_satisfied(draft: InquiryDraft) -> bool:
    return _has_value(draft, FieldKey.MOBILE) or _has_value(draft, FieldKey.LANDLINE)


def _is_unconfirmed(draft: InquiryDraft, key: FieldKey) -> bool:
    field = draft.fields[key]
    if field.value is None:
        return False
    if isinstance(field.value, str) and not field.value.strip():
        return False
    if isinstance(field.value, list) and len(field.value) == 0:
        return False
    return field.source in NEEDS_CONFIRMATION and not field.confirmed


def verification_blockers(draft: InquiryDraft) -> list[Blocker]:
    """Contact verification still pending: email always, mobile only when one is given."""
    blockers: list[Blocker] = []
    if not draft.email_verified:
        blockers.append(Blocker.email_not_verified())
    if _has_value(draft, FieldKey.MOBILE) and not draft.mobile_verified:
        blockers.append(Blocker.mobile_not_verified())
    return blockers


def contact_verified(draft: InquiryDraft) -> bool:
    return not verification_blockers(draft)


def can_submit(draft: InquiryDraft) -> list[Blocker]:
    blockers: list[Blocker] = []

    if draft.cr_status == "existing":
        blockers.append(Blocker.cr_existing())

    if draft.cr_status == "unknown":
        blockers.append(Blocker.cr_pending())

    for definition in FIELD_BY_KEY.values():
        if definition.group == FieldGroup.DOCUMENTS:
            continue
        if definition.key in (FieldKey.MOBILE, FieldKey.LANDLINE):
            continue
        if definition.required and not _has_value(draft, definition.key):
            blockers.append(Blocker.missing_field(definition.key.value))

    if not _contact_satisfied(draft):
        blockers.append(Blocker.missing_field("contact"))

    for definition in FIELD_BY_KEY.values():
        if definition.group == FieldGroup.DOCUMENTS:
            continue
        if _is_unconfirmed(draft, definition.key):
            blockers.append(Blocker.unconfirmed_field(definition.key.value))

    blockers.extend(verification_blockers(draft))

    for doc_type, _label, required in document_definitions():
        if required and doc_type not in draft.documents:
            blockers.append(Blocker.missing_document(doc_type))

    if not draft.terms_accepted:
        blockers.append(Blocker.terms_not_accepted())

    if draft.intake_flow == "v2":
        # Flow v2 (§3.3): blockers follow the app's section order.
        return sorted(blockers, key=_v2_blocker_rank)
    return blockers


def _v2_blocker_rank(blocker: Blocker) -> int:
    from app.domain.sections import SECTION_OF, IntakeSection, section_rank

    kind, _sep, key = blocker.token.partition(":")
    if kind in ("cr_pending", "cr_existing"):
        section = IntakeSection.COMPANY_REGISTRATION
    elif kind in ("missing_field", "unconfirmed_field"):
        section = (
            IntakeSection.BASIC_INFO
            if key == "contact"
            else SECTION_OF.get(FieldKey(key), IntakeSection.BASIC_INFO)
        )
    elif kind in ("email_not_verified", "mobile_not_verified"):
        section = IntakeSection.VERIFICATION
    elif kind == "terms_not_accepted":
        section = IntakeSection.TERMS
    else:
        section = IntakeSection.DOCUMENTS
    return section_rank(section)


RemainingStep = Literal[
    "cr",
    "fields",
    "verify_email",
    "verify_mobile",
    "documents",
    "terms",
    # Flow v2 (§3.3): the field steps by section.
    "unit_and_category",
    "basic_info",
    "property_details",
]


def open_fields(draft: InquiryDraft) -> tuple[list[str], list[str]]:
    """The field keys behind the `fields` step, from `can_submit`: (missing, unconfirmed).
    `contact` stands for a mobile or landline."""
    missing: list[str] = []
    unconfirmed: list[str] = []
    for blocker in can_submit(draft):
        kind, _sep, key = blocker.token.partition(":")
        if kind == "missing_field" and key not in missing:
            missing.append(key)
        elif kind == "unconfirmed_field" and key not in unconfirmed:
            unconfirmed.append(key)
    return missing, unconfirmed


def remaining_steps(draft: InquiryDraft) -> list[RemainingStep]:
    """What is still needed before submit, derived from `can_submit`, in the usual order.

    The user can do these in any order (documents before verification is fine); the
    list says what is left, not what comes next in a script. Empty once submitted or
    when the CR already has an account (nothing to submit here).
    """
    if draft.reference or draft.cr_status == "existing":
        return []
    if draft.intake_flow == "v2":
        return _v2_remaining_steps(draft)
    tokens = [b.token for b in can_submit(draft)]
    steps: list[RemainingStep] = []
    if "cr_pending" in tokens:
        steps.append("cr")
    if any(t.startswith(("missing_field:", "unconfirmed_field:")) for t in tokens):
        steps.append("fields")
    if "email_not_verified" in tokens:
        steps.append("verify_email")
    if "mobile_not_verified" in tokens:
        steps.append("verify_mobile")
    if any(t.startswith("missing_document:") for t in tokens):
        steps.append("documents")
    if "terms_not_accepted" in tokens:
        steps.append("terms")
    return steps


def _v2_remaining_steps(draft: InquiryDraft) -> list[RemainingStep]:
    """Flow v2 (§3.3): what's left in the app's section order: cr, unit_and_category,
    basic_info, verify_email, verify_mobile, property_details, terms, documents."""
    from app.domain.sections import IntakeSection, section_done

    steps: list[RemainingStep] = []
    if not section_done(draft, IntakeSection.COMPANY_REGISTRATION):
        steps.append("cr")
    if not section_done(draft, IntakeSection.UNIT_AND_CATEGORY):
        steps.append("unit_and_category")
    if not section_done(draft, IntakeSection.BASIC_INFO):
        steps.append("basic_info")
    for blocker in verification_blockers(draft):
        steps.append("verify_email" if blocker.token == "email_not_verified" else "verify_mobile")
    if not section_done(draft, IntakeSection.PROPERTY_DETAILS):
        steps.append("property_details")
    if not draft.terms_accepted:
        steps.append("terms")
    if not section_done(draft, IntakeSection.DOCUMENTS):
        steps.append("documents")
    return steps


def compute_phase(draft: InquiryDraft) -> Phase:
    if draft.cr_status == "existing":
        return Phase.EXISTING_ACCOUNT
    if draft.reference:
        return Phase.SUBMITTED
    if draft.cr_status == "unknown":
        return Phase.GATE
    if draft.intake_flow == "v2":
        return _v2_phase(draft)

    blockers = can_submit(draft)
    collecting_tokens = {
        b.token
        for b in blockers
        if b.token.startswith("missing_field:") or b.token.startswith("unconfirmed_field:")
    }
    if collecting_tokens:
        return Phase.COLLECTING

    if not contact_verified(draft):
        return Phase.VERIFYING

    doc_blockers = [b for b in blockers if b.token.startswith("missing_document:")]
    if doc_blockers:
        return Phase.DOCUMENTS

    return Phase.REVIEW


def _v2_phase(draft: InquiryDraft) -> Phase:
    """Flow v2 (§3.3): `phase` keeps its values; `collecting` covers Unit Type and Sales
    Category, Basic Info and Property Details; `documents` covers the terms and documents."""
    from app.domain.sections import IntakeSection, current_section

    section = current_section(draft)
    if section is IntakeSection.VERIFICATION:
        return Phase.VERIFYING
    if section in (IntakeSection.TERMS, IntakeSection.DOCUMENTS):
        return Phase.DOCUMENTS
    if section is IntakeSection.REVIEW:
        return Phase.REVIEW
    return Phase.COLLECTING
