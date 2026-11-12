"""The app's Send Inquiry sections, in order (spec flow-v2-alignment §3.3; day F3).

Flow v2 public intake (`InquiryDraft.intake_flow == "v2"`) asks one section at a time in
the app's order. This module says, from the draft alone, which sections are done and which
one is current; the summary, the bundle hint, the guard and the submit rules read it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.fields import document_definitions
from app.domain.models import NEEDS_CONFIRMATION, FieldKey, InquiryDraft


class IntakeSection(StrEnum):
    COMPANY_REGISTRATION = "company_registration"
    UNIT_AND_CATEGORY = "unit_and_category"
    BASIC_INFO = "basic_info"
    VERIFICATION = "verification"
    PROPERTY_DETAILS = "property_details"
    TERMS = "terms"
    DOCUMENTS = "documents"
    REVIEW = "review"


SECTION_ORDER: tuple[IntakeSection, ...] = tuple(IntakeSection)

SECTION_LABELS: dict[IntakeSection, str] = {
    IntakeSection.COMPANY_REGISTRATION: "Company Registration",
    IntakeSection.UNIT_AND_CATEGORY: "Unit Type and Sales Category",
    IntakeSection.BASIC_INFO: "Basic Info",
    IntakeSection.VERIFICATION: "Email/Mobile Verification",
    IntakeSection.PROPERTY_DETAILS: "Property Details",
    IntakeSection.TERMS: "Terms and privacy",
    IntakeSection.DOCUMENTS: "Documents",
    IntakeSection.REVIEW: "Review and submit",
}

UNIT_AND_CATEGORY_KEYS: tuple[FieldKey, ...] = (FieldKey.UNIT_TYPE, FieldKey.SALES_CATEGORY)
BASIC_INFO_KEYS: tuple[FieldKey, ...] = (
    FieldKey.FIRST_NAME,
    FieldKey.LAST_NAME,
    FieldKey.COMPANY_NAME,
    FieldKey.COMPANY_ADDRESS,
    FieldKey.BRAND_NAME_EN,
    FieldKey.BRAND_NAME_AR,
    FieldKey.EMAIL,
)
PROPERTY_KEYS: tuple[FieldKey, ...] = (
    FieldKey.MALLS,
    FieldKey.LEASE_PERIOD,
    FieldKey.AREA_MIN,
    FieldKey.AREA_MAX,
    FieldKey.RENT_PERIOD,
    FieldKey.RENT_MIN,
    FieldKey.RENT_MAX,
)

# The section each field belongs to; a field given early is saved, never asked again.
SECTION_OF: dict[FieldKey, IntakeSection] = {
    FieldKey.CR_NUMBER: IntakeSection.COMPANY_REGISTRATION,
    **dict.fromkeys(UNIT_AND_CATEGORY_KEYS, IntakeSection.UNIT_AND_CATEGORY),
    **dict.fromkeys(BASIC_INFO_KEYS, IntakeSection.BASIC_INFO),
    FieldKey.MOBILE: IntakeSection.BASIC_INFO,
    FieldKey.LANDLINE: IntakeSection.BASIC_INFO,
    **dict.fromkeys(PROPERTY_KEYS, IntakeSection.PROPERTY_DETAILS),
    FieldKey.VAT_NUMBER: IntakeSection.DOCUMENTS,
    FieldKey.NATIONAL_ID_NUMBER: IntakeSection.DOCUMENTS,
    FieldKey.NATIONAL_ADDRESS: IntakeSection.DOCUMENTS,
}


def _has_value(draft: InquiryDraft, key: FieldKey) -> bool:
    value = draft.fields[key].value
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return not (isinstance(value, list) and not value)


def _settled(draft: InquiryDraft, key: FieldKey) -> bool:
    """Set, and confirmed when its source needs it."""
    field = draft.fields[key]
    return _has_value(draft, key) and (field.source not in NEEDS_CONFIRMATION or field.confirmed)


def _unconfirmed(draft: InquiryDraft, key: FieldKey) -> bool:
    field = draft.fields[key]
    return _has_value(draft, key) and field.source in NEEDS_CONFIRMATION and not field.confirmed


def missing_in(draft: InquiryDraft, section: IntakeSection) -> list[str]:
    """The field keys this section still needs (missing or unconfirmed); `contact` stands
    for a mobile or landline."""
    if section is IntakeSection.UNIT_AND_CATEGORY:
        return [k.value for k in UNIT_AND_CATEGORY_KEYS if not _settled(draft, k)]
    if section is IntakeSection.BASIC_INFO:
        left = [k.value for k in BASIC_INFO_KEYS if not _settled(draft, k)]
        phones = (FieldKey.MOBILE, FieldKey.LANDLINE)
        if not any(_has_value(draft, k) for k in phones):
            left.append("contact")
        left += [k.value for k in phones if _unconfirmed(draft, k)]
        return left
    if section is IntakeSection.PROPERTY_DETAILS:
        left = [] if _settled(draft, FieldKey.MALLS) else [FieldKey.MALLS.value]
        return left + [k.value for k in PROPERTY_KEYS[1:] if _unconfirmed(draft, k)]
    return []


def section_done(draft: InquiryDraft, section: IntakeSection) -> bool:
    if section is IntakeSection.COMPANY_REGISTRATION:
        return draft.cr_status in ("new", "skipped")
    if section in (
        IntakeSection.UNIT_AND_CATEGORY,
        IntakeSection.BASIC_INFO,
        IntakeSection.PROPERTY_DETAILS,
    ):
        return not missing_in(draft, section)
    if section is IntakeSection.VERIFICATION:
        mobile_ok = not _has_value(draft, FieldKey.MOBILE) or draft.mobile_verified
        return draft.email_verified and mobile_ok
    if section is IntakeSection.TERMS:
        return draft.terms_accepted
    if section is IntakeSection.DOCUMENTS:
        return all(
            doc_type in draft.documents
            for doc_type, _label, required in document_definitions()
            if required
        )
    return bool(draft.reference)


def current_section(draft: InquiryDraft) -> IntakeSection:
    """The first section not done (`review` once everything before it is)."""
    for section in SECTION_ORDER:
        if not section_done(draft, section):
            return section
    return IntakeSection.REVIEW


def section_rank(section: IntakeSection) -> int:
    return SECTION_ORDER.index(section)


@dataclass(frozen=True)
class SectionState:
    key: str
    label: str
    done: bool


def section_states(draft: InquiryDraft) -> list[SectionState]:
    return [
        SectionState(key=s.value, label=SECTION_LABELS[s], done=section_done(draft, s))
        for s in SECTION_ORDER
    ]
