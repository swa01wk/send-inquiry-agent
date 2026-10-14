"""Draft summary for API/SSE and agent prompt block."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.fields import (
    DOCUMENT_DEFINITIONS,
    FIELD_BY_KEY,
    GROUP_ORDER,
    FieldGroup,
    display_area,
    display_lease,
    display_rent,
)
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft, Source
from app.domain.rules import can_submit, compute_phase


class DraftFieldRow(BaseModel):
    key: str
    label: str
    group: str
    display: str | None
    source: str | None
    confirmed: bool
    required: bool


class DraftDocumentRow(BaseModel):
    doc_type: str
    label: str
    required: bool
    uploaded: bool
    file_name: str | None
    size_bytes: int | None


class DraftChecks(BaseModel):
    required_filled: int
    required_total: int = 11
    unconfirmed: int
    otp_verified: bool
    required_docs_uploaded: int
    required_docs_total: int = 2
    terms_accepted: bool


class DraftSummary(BaseModel):
    phase: str
    fields: list[DraftFieldRow]
    documents: list[DraftDocumentRow]
    checks: DraftChecks
    can_submit: bool
    changed_keys: list[str] = Field(default_factory=list)


REQUIRED_SLOT_KEYS: list[FieldKey | str] = [
    FieldKey.COMPANY_NAME,
    FieldKey.COMPANY_ADDRESS,
    FieldKey.BRAND_NAME_EN,
    FieldKey.BRAND_NAME_AR,
    FieldKey.UNIT_TYPE,
    FieldKey.SALES_CATEGORY,
    FieldKey.MALLS,
    FieldKey.FIRST_NAME,
    FieldKey.LAST_NAME,
    FieldKey.EMAIL,
    "contact",
]

SPACE_SKIP_IN_LIST = {
    FieldKey.AREA_MIN,
    FieldKey.AREA_MAX,
    FieldKey.RENT_MIN,
    FieldKey.RENT_MAX,
    FieldKey.RENT_PERIOD,
    FieldKey.LEASE_PERIOD,
}


def _field_required(key: FieldKey) -> bool:
    return FIELD_BY_KEY[key].required


def _count_required_filled(draft: InquiryDraft) -> int:
    filled = 0
    for slot in REQUIRED_SLOT_KEYS:
        if slot == "contact":
            if _has_contact(draft):
                filled += 1
        elif isinstance(slot, FieldKey) and _has_field_value(draft, slot):
            filled += 1
    return filled


def _has_contact(draft: InquiryDraft) -> bool:
    for key in (FieldKey.MOBILE, FieldKey.LANDLINE):
        if _has_field_value(draft, key):
            return True
    return False


def _has_field_value(draft: InquiryDraft, key: FieldKey) -> bool:
    val = draft.fields[key].value
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    if isinstance(val, list) and len(val) == 0:
        return False
    return True


def _count_unconfirmed(draft: InquiryDraft) -> int:
    count = 0
    for key in FieldKey:
        field = draft.fields[key]
        if field.value is None:
            continue
        if isinstance(field.value, str) and not field.value.strip():
            continue
        if field.source in (Source.DERIVED, Source.VERIFIED) and not field.confirmed:
            count += 1
    return count


def _composite_row(
    *,
    key: str,
    label: str,
    display: str | None,
    draft: InquiryDraft,
    keys: list[FieldKey],
    required: bool,
) -> DraftFieldRow:
    source_values: list[str] = []
    for field_key in keys:
        src = draft.fields[field_key].source
        if src is not None:
            source_values.append(src.value)
    source = source_values[0] if source_values else None
    confirmed = all(
        draft.fields[field_key].confirmed
        for field_key in keys
        if draft.fields[field_key].value is not None
    )
    if display is None:
        confirmed = True
        source = None
    return DraftFieldRow(
        key=key,
        label=label,
        group=FieldGroup.SPACE.value,
        display=display,
        source=source,
        confirmed=confirmed,
        required=required,
    )


def build_draft_summary(
    draft: InquiryDraft,
    master: MasterData,
    changed_keys: list[str] | None = None,
) -> DraftSummary:
    phase = compute_phase(draft)
    blockers = can_submit(draft)
    rows: list[DraftFieldRow] = []

    for group in GROUP_ORDER:
        for definition in FIELD_BY_KEY.values():
            if definition.group != group:
                continue
            if definition.key in SPACE_SKIP_IN_LIST:
                continue
            if definition.group == FieldGroup.DOCUMENTS:
                continue
            field = draft.fields[definition.key]
            rows.append(
                DraftFieldRow(
                    key=definition.key.value,
                    label=definition.label,
                    group=definition.group.value,
                    display=definition.display(draft, master),
                    source=field.source.value if field.source else None,
                    confirmed=field.confirmed,
                    required=definition.required,
                )
            )
        if group == FieldGroup.SPACE:
            rows.append(
                _composite_row(
                    key="area",
                    label="Area",
                    display=display_area(draft),
                    draft=draft,
                    keys=[FieldKey.AREA_MIN, FieldKey.AREA_MAX],
                    required=False,
                )
            )
            rows.append(
                _composite_row(
                    key="rent",
                    label="Rent",
                    display=display_rent(draft, master),
                    draft=draft,
                    keys=[FieldKey.RENT_MIN, FieldKey.RENT_MAX, FieldKey.RENT_PERIOD],
                    required=False,
                )
            )
            rows.append(
                _composite_row(
                    key="lease",
                    label="Lease period",
                    display=display_lease(draft, master),
                    draft=draft,
                    keys=[FieldKey.LEASE_PERIOD],
                    required=False,
                )
            )

    documents: list[DraftDocumentRow] = []
    required_docs_uploaded = 0
    for doc_type, label, required in DOCUMENT_DEFINITIONS:
        ref = draft.documents.get(doc_type)
        uploaded = ref is not None
        if required and uploaded:
            required_docs_uploaded += 1
        documents.append(
            DraftDocumentRow(
                doc_type=doc_type.value,
                label=label,
                required=required,
                uploaded=uploaded,
                file_name=ref.file_name if ref else None,
                size_bytes=ref.size_bytes if ref else None,
            )
        )

    checks = DraftChecks(
        required_filled=_count_required_filled(draft),
        unconfirmed=_count_unconfirmed(draft),
        otp_verified=draft.otp_verified,
        required_docs_uploaded=required_docs_uploaded,
        terms_accepted=draft.terms_accepted,
    )

    return DraftSummary(
        phase=phase.value,
        fields=rows,
        documents=documents,
        checks=checks,
        can_submit=len(blockers) == 0,
        changed_keys=list(changed_keys or []),
    )


def prompt_summary(draft: InquiryDraft, master: MasterData) -> str:
    summary = build_draft_summary(draft, master)
    phase = summary.phase

    collected_parts: list[str] = []
    for row in summary.fields:
        if not row.display:
            continue
        src = row.source or "unknown"
        state = "confirmed" if row.confirmed else "unconfirmed"
        collected_parts.append(f"{row.label}={row.display} ({src}, {state})")

    missing_labels: list[str] = []
    for slot in REQUIRED_SLOT_KEYS:
        if slot == "contact":
            if not _has_contact(draft):
                missing_labels.append("Mobile or landline")
            continue
        if isinstance(slot, FieldKey) and not _has_field_value(draft, slot):
            missing_labels.append(FIELD_BY_KEY[slot].label)

    needs_confirmation: list[str] = []
    for row in summary.fields:
        if row.display and row.source in ("derived", "verified") and not row.confirmed:
            needs_confirmation.append(row.label)

    collected = ", ".join(collected_parts) if collected_parts else "none"
    missing = ", ".join(missing_labels) if missing_labels else "none"
    confirm = ", ".join(needs_confirmation) if needs_confirmation else "none"
    otp = "yes" if draft.otp_verified else "no"
    terms = "yes" if draft.terms_accepted else "no"
    docs = f"{summary.checks.required_docs_uploaded}/{summary.checks.required_docs_total}"

    return (
        f"Current phase: {phase}\n"
        f"Collected: {collected}\n"
        f"Missing required: {missing}\n"
        f"Needs confirmation: {confirm}\n"
        f"OTP verified: {otp} · Required documents: {docs} · Terms accepted: {terms}"
    )
