"""Pure draft mutations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain import validation as v
from app.domain.fields import FIELD_BY_KEY
from app.domain.master import MasterData
from app.domain.models import (
    DocType,
    DocumentRef,
    FieldKey,
    FieldValue,
    InquiryDraft,
    Source,
    WriteKey,
    new_inquiry_draft,
)
from app.domain.rules import contact_verified

WriteEntry = tuple[str, Any, Source]


def write_fields(
    draft: InquiryDraft,
    entries: list[WriteEntry],
    *,
    master: MasterData,
    evidence: dict[str, str] | None = None,
) -> tuple[InquiryDraft, list[str], dict[str, v.ValidationError]]:
    """Validate and write entries. `evidence` (key → the user's words) applies to derived
    entries only; any other write clears a field's evidence."""
    updated = draft.model_copy(deep=True)
    quotes = evidence or {}
    written_keys: list[str] = []
    errors: dict[str, v.ValidationError] = {}

    for key_str, value, source in entries:
        if key_str == WriteKey.CONTACT_NUMBER.value:
            classified = v.classify_contact_number(str(value))
            if isinstance(classified, v.ValidationError):
                errors[key_str] = classified
                continue
            contact_kind, normalised = classified
            target = FieldKey.MOBILE if contact_kind == "mobile" else FieldKey.LANDLINE
            _apply_field(updated, target, normalised, source, written_keys, errors, master)
            continue

        try:
            field_key = FieldKey(key_str)
        except ValueError:
            errors[key_str] = v.ValidationError(
                code="unknown_field",
                message=f"Unknown field: {key_str}",
            )
            continue

        _apply_field(
            updated,
            field_key,
            value,
            source,
            written_keys,
            errors,
            master,
            evidence=quotes.get(key_str) if source == Source.DERIVED else None,
        )

    cross_errors = _cross_validate(updated, master)
    errors.update(cross_errors)

    deduped: list[str] = []
    seen: set[str] = set()
    for key in written_keys:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    return updated, deduped, errors


def _apply_field(
    draft: InquiryDraft,
    key: FieldKey,
    value: Any,
    source: Source,
    written_keys: list[str],
    errors: dict[str, v.ValidationError],
    master: MasterData,
    *,
    evidence: str | None = None,
) -> None:
    definition = FIELD_BY_KEY.get(key)
    if definition is None:
        errors[key.value] = v.ValidationError(
            code="unknown_field",
            message=f"Unknown field: {key.value}",
        )
        return

    if source not in (Source.USER, Source.DERIVED, Source.VERIFIED, Source.DEFAULT):
        errors[key.value] = v.ValidationError(
            code="invalid_source",
            message="Invalid source for field write.",
        )
        return

    if value is None or value == "":
        if definition.required:
            errors[key.value] = v.ValidationError(
                code="missing_value",
                message=f"{definition.label} is required.",
            )
        else:
            previous = draft.fields[key].value
            draft.fields[key] = FieldValue(value=None, source=None, confirmed=False)
            _reset_verification_if_changed(draft, key, previous, None)
            written_keys.append(key.value)
        return

    validated = definition.validator(value, master)
    if isinstance(validated, v.ValidationError):
        errors[key.value] = validated
        return
    if validated == "" and not definition.required:
        draft.fields[key] = FieldValue(value=None, source=None, confirmed=False)
        written_keys.append(key.value)
        return

    current = draft.fields[key]
    if current.value is not None and validated == current.value:
        if evidence and current.source == Source.DERIVED and not current.evidence:
            draft.fields[key] = current.model_copy(update={"evidence": evidence})
        return

    confirmed = source in (Source.USER, Source.DEFAULT)
    previous = draft.fields[key].value
    draft.fields[key] = FieldValue(
        value=validated,
        source=source,
        confirmed=confirmed,
        evidence=evidence if source == Source.DERIVED else None,
    )
    _reset_verification_if_changed(draft, key, previous, validated)
    written_keys.append(key.value)


def _reset_verification_if_changed(
    draft: InquiryDraft,
    key: FieldKey,
    previous: Any,
    current: Any,
) -> None:
    """A verified email or mobile no longer counts once it changes."""
    if previous == current:
        return
    if key in (FieldKey.EMAIL, FieldKey.MOBILE):
        draft.verified_at = None
    if key == FieldKey.EMAIL:
        draft.email_verified = False
        draft.email_link_sent_to = None
    elif key == FieldKey.MOBILE:
        draft.mobile_verified = False
        draft.otp_sent_to = None
        draft.otp_attempts_left = 3


def _cross_validate(draft: InquiryDraft, master: MasterData) -> dict[str, v.ValidationError]:
    errors: dict[str, v.ValidationError] = {}
    area_min = draft.fields[FieldKey.AREA_MIN].value
    area_max = draft.fields[FieldKey.AREA_MAX].value
    if area_err := v.validate_area_range(area_min, area_max):
        errors["area"] = area_err

    rent_min = draft.fields[FieldKey.RENT_MIN].value
    rent_max = draft.fields[FieldKey.RENT_MAX].value
    if rent_err := v.validate_rent_range(rent_min, rent_max):
        errors["rent"] = rent_err
    rent_period = draft.fields[FieldKey.RENT_PERIOD].value
    if period_err := v.validate_rent_period_required(rent_period, rent_min, rent_max):
        errors[FieldKey.RENT_PERIOD.value] = period_err

    malls = draft.fields[FieldKey.MALLS].value
    if malls is not None:
        mall_check = v.validate_malls(malls, master)
        if isinstance(mall_check, v.ValidationError):
            errors[FieldKey.MALLS.value] = mall_check

    return errors


# What a follow-on inquiry reuses from the inquiry it follows (L3 §3.11).
FOLLOW_ON_FIELDS: tuple[FieldKey, ...] = (
    FieldKey.CR_NUMBER,
    FieldKey.COMPANY_NAME,
    FieldKey.COMPANY_ADDRESS,
    FieldKey.BRAND_NAME_EN,
    FieldKey.BRAND_NAME_AR,
    FieldKey.UNIT_TYPE,
    FieldKey.SALES_CATEGORY,
    FieldKey.FIRST_NAME,
    FieldKey.LAST_NAME,
    FieldKey.EMAIL,
    FieldKey.MOBILE,
    FieldKey.LANDLINE,
)
FOLLOW_ON_DOCUMENTS: tuple[DocType, ...] = (DocType.COMPANY_PROFILE, DocType.BRAND_PROFILE)


def follow_on_draft(
    previous: InquiryDraft,
    *,
    reuse_hours: int,
    now: datetime | None = None,
) -> tuple[InquiryDraft, list[str], bool]:
    """A new inquiry prefilled from a submitted one: (draft, copied keys, verification reused).

    Company, brand, unit type, sales category and contact are copied as `verified` and
    unconfirmed, so the user confirms them (one card). Company Profile and Brand Profile
    are reused by reference. The contact stays verified when the earlier inquiry was
    verified within `reuse_hours`; changing the email or mobile clears it as usual.
    """
    current = now or datetime.now(tz=UTC)
    draft = new_inquiry_draft()
    copied: list[str] = []
    for key in FOLLOW_ON_FIELDS:
        old = previous.fields[key]
        if old.value is None or old.value == "" or old.value == []:
            continue
        draft.fields[key] = FieldValue(value=old.value, source=Source.VERIFIED, confirmed=False)
        copied.append(key.value)
    if previous.cr_status in ("new", "skipped"):
        draft.cr_status = previous.cr_status
    for doc_type in FOLLOW_ON_DOCUMENTS:
        ref = previous.documents.get(doc_type)
        if ref is not None:
            draft.documents[doc_type] = ref.model_copy(
                update={"copied_from": ref.copied_from or previous.reference}
            )
    reuse = (
        previous.verified_at is not None
        and contact_verified(previous)
        and current - previous.verified_at <= timedelta(hours=reuse_hours)
    )
    if reuse:
        draft.email_verified = previous.email_verified
        draft.mobile_verified = previous.mobile_verified
        draft.email_link_sent_to = previous.email_link_sent_to
        draft.otp_sent_to = previous.otp_sent_to
        draft.verified_at = previous.verified_at
    draft.follow_on_of = previous.reference
    return draft, copied, reuse


def stamp_verified(draft: InquiryDraft, now: datetime | None = None) -> None:
    """Record when the contact became fully verified (email, and mobile when given)."""
    if draft.verified_at is None and contact_verified(draft):
        draft.verified_at = now or datetime.now(tz=UTC)


def confirm(draft: InquiryDraft, keys: list[str]) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    for key_str in keys:
        try:
            key = FieldKey(key_str)
        except ValueError:
            continue
        field = updated.fields[key]
        if field.value is not None and field.source in (Source.DERIVED, Source.VERIFIED):
            field.confirmed = True
    return updated


def add_document(
    draft: InquiryDraft,
    doc_type: DocType,
    *,
    file_id: str,
    file_name: str,
    size_bytes: int,
    max_bytes: int,
    uploaded_at: datetime | None = None,
) -> tuple[InquiryDraft, v.ValidationError | None]:
    if ext_err := v.validate_document_extension(file_name):
        return draft, ext_err
    if size_err := v.validate_document_size(size_bytes, max_bytes):
        return draft, size_err

    updated = draft.model_copy(deep=True)
    updated.documents[doc_type] = DocumentRef(
        doc_type=doc_type,
        file_id=file_id,
        file_name=file_name,
        size_bytes=size_bytes,
        uploaded_at=uploaded_at or datetime.now(tz=UTC),
    )
    return updated, None


def remove_document(draft: InquiryDraft, doc_type: DocType) -> InquiryDraft:
    updated = draft.model_copy(deep=True)
    updated.documents.pop(doc_type, None)
    return updated


__all__ = [
    "new_inquiry_draft",
    "write_fields",
    "confirm",
    "add_document",
    "remove_document",
    "stamp_verified",
    "follow_on_draft",
]
