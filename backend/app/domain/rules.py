"""Submit rules and phase computation."""

from __future__ import annotations

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

    return blockers


def compute_phase(draft: InquiryDraft) -> Phase:
    if draft.cr_status == "existing":
        return Phase.EXISTING_ACCOUNT
    if draft.reference:
        return Phase.SUBMITTED
    if draft.cr_status == "unknown":
        return Phase.GATE

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
