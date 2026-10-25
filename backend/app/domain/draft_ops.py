"""Pure draft mutations."""

from __future__ import annotations

from datetime import UTC, datetime
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

WriteEntry = tuple[str, Any, Source]


def write_fields(
    draft: InquiryDraft,
    entries: list[WriteEntry],
    *,
    master: MasterData,
) -> tuple[InquiryDraft, list[str], dict[str, v.ValidationError]]:
    updated = draft.model_copy(deep=True)
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
            written_keys.append(target.value)
            continue

        try:
            field_key = FieldKey(key_str)
        except ValueError:
            errors[key_str] = v.ValidationError(
                code="unknown_field",
                message=f"Unknown field: {key_str}",
            )
            continue

        _apply_field(updated, field_key, value, source, written_keys, errors, master)

    cross_errors = _cross_validate(updated, master)
    errors.update(cross_errors)

    return updated, written_keys, errors


def _apply_field(
    draft: InquiryDraft,
    key: FieldKey,
    value: Any,
    source: Source,
    written_keys: list[str],
    errors: dict[str, v.ValidationError],
    master: MasterData,
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

    confirmed = source in (Source.USER, Source.DEFAULT)
    previous = draft.fields[key].value
    draft.fields[key] = FieldValue(value=validated, source=source, confirmed=confirmed)
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


__all__ = ["new_inquiry_draft", "write_fields", "confirm", "add_document", "remove_document"]
