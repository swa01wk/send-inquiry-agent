"""Domain models for the inquiry draft."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(StrEnum):
    USER = "user"
    DERIVED = "derived"
    VERIFIED = "verified"
    DEFAULT = "default"


class FieldKey(StrEnum):
    CR_NUMBER = "cr_number"
    COMPANY_NAME = "company_name"
    COMPANY_ADDRESS = "company_address"
    BRAND_NAME_EN = "brand_name_en"
    BRAND_NAME_AR = "brand_name_ar"
    UNIT_TYPE = "unit_type"
    SALES_CATEGORY = "sales_category"
    MALLS = "malls"
    AREA_MIN = "area_min"
    AREA_MAX = "area_max"
    RENT_PERIOD = "rent_period"
    RENT_MIN = "rent_min"
    RENT_MAX = "rent_max"
    LEASE_PERIOD = "lease_period"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    MOBILE = "mobile"
    LANDLINE = "landline"
    VAT_NUMBER = "vat_number"
    NATIONAL_ID_NUMBER = "national_id_number"
    NATIONAL_ADDRESS = "national_address"


class WriteKey(StrEnum):
    """Keys accepted by write_fields (includes pseudo keys)."""

    CONTACT_NUMBER = "contact_number"


class DocType(StrEnum):
    COMPANY_PROFILE = "company_profile"
    BRAND_PROFILE = "brand_profile"
    CR_CERTIFICATE = "cr_certificate"
    VAT_CERTIFICATE = "vat_certificate"
    NATIONAL_ID = "national_id"
    NATIONAL_ADDRESS = "national_address"
    ARTICLES_OF_ASSOCIATION = "articles_of_association"


class Phase(StrEnum):
    EXISTING_ACCOUNT = "existing_account"
    SUBMITTED = "submitted"
    GATE = "gate"
    COLLECTING = "collecting"
    VERIFYING = "verifying"
    DOCUMENTS = "documents"
    REVIEW = "review"


CrStatus = Literal["unknown", "new", "existing", "skipped"]


EVIDENCE_MAX_CHARS = 80


class FieldValue(BaseModel):
    value: Any | None = None
    source: Source | None = None
    confirmed: bool = False
    # For derived values: the user's words the value came from (L3 §3.9), shown on the
    # confirm card ("from: '…'") and kept in the audit trail for reviewers.
    evidence: str | None = None


class DocumentRef(BaseModel):
    doc_type: DocType
    file_id: str
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    # Reused from an earlier inquiry (its reference) by a follow-on inquiry (L3 §3.11).
    copied_from: str | None = None


class Blocker(BaseModel):
    """Submit blocker; `token` matches spec codes like missing_field:company_name."""

    token: str

    @classmethod
    def cr_existing(cls) -> Blocker:
        return cls(token="cr_existing")

    @classmethod
    def cr_pending(cls) -> Blocker:
        return cls(token="cr_pending")

    @classmethod
    def missing_field(cls, key: str) -> Blocker:
        return cls(token=f"missing_field:{key}")

    @classmethod
    def unconfirmed_field(cls, key: str) -> Blocker:
        return cls(token=f"unconfirmed_field:{key}")

    @classmethod
    def email_not_verified(cls) -> Blocker:
        return cls(token="email_not_verified")

    @classmethod
    def mobile_not_verified(cls) -> Blocker:
        return cls(token="mobile_not_verified")

    @classmethod
    def missing_document(cls, doc_type: DocType) -> Blocker:
        return cls(token=f"missing_document:{doc_type.value}")

    @classmethod
    def terms_not_accepted(cls) -> Blocker:
        return cls(token="terms_not_accepted")


class InquiryDraft(BaseModel):
    fields: dict[FieldKey, FieldValue]
    cr_status: CrStatus = "unknown"
    documents: dict[DocType, DocumentRef] = Field(default_factory=dict)
    # Email is verified by a one-time link; the mobile (when given) by an OTP code.
    # A landline-only applicant is verified by email alone. Changing the email or
    # mobile clears that channel's verification (see draft_ops.write_fields).
    email_verified: bool = False
    mobile_verified: bool = False
    email_link_sent_to: str | None = None
    otp_sent_to: str | None = None
    otp_attempts_left: int = 3
    terms_accepted: bool = False
    reference: str | None = None
    # When the contact became fully verified (decides follow-on reuse, L3 §3.11).
    verified_at: datetime | None = None
    # The submitted inquiry this one follows on from (same chat, another mall).
    follow_on_of: str | None = None


def new_inquiry_draft() -> InquiryDraft:
    fields: dict[FieldKey, FieldValue] = {key: FieldValue() for key in FieldKey}
    fields[FieldKey.AREA_MIN] = FieldValue(value=10, source=Source.DEFAULT, confirmed=True)
    fields[FieldKey.AREA_MAX] = FieldValue(value=25000, source=Source.DEFAULT, confirmed=True)
    return InquiryDraft(fields=fields)
