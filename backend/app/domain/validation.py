"""Field and document validation."""

from __future__ import annotations

import re
from typing import Literal, TypeVar

from pydantic import BaseModel, EmailStr, TypeAdapter

from app.domain.master import MasterData
from app.policy.config import get_policy

T = TypeVar("T")

_EMAIL_ADAPTER: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)

CR_NUMBER_RE = re.compile(r"^\d{10}$")
VAT_RE = re.compile(r"^3\d{13}3$")
NATIONAL_ID_RE = re.compile(r"^[12]\d{9}$")
LATIN_RE = re.compile(r"^[A-Za-z0-9\s&'.,\-()]+$")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
ALLOWED_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "doc", "docx", "xlsx", "zip"})


class ValidationError(BaseModel):
    code: str
    message: str


def is_validation_error(result: T | ValidationError) -> bool:
    return isinstance(result, ValidationError)


def validate_cr_number(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not CR_NUMBER_RE.match(value):
        return ValidationError(code="invalid_cr_number", message="CR number must be 10 digits.")
    return value


def validate_company_name(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not 2 <= len(value) <= 120:
        return ValidationError(
            code="invalid_company_name",
            message="Company name must be between 2 and 120 characters.",
        )
    return value


def validate_company_address(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not 5 <= len(value) <= 250:
        return ValidationError(
            code="invalid_company_address",
            message="Company address must be between 5 and 250 characters.",
        )
    return value


def validate_brand_name_en(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not 1 <= len(value) <= 80:
        return ValidationError(
            code="invalid_brand_name_en",
            message="Brand name (EN) must be between 1 and 80 characters.",
        )
    if not LATIN_RE.match(value):
        return ValidationError(
            code="invalid_brand_name_en",
            message="Brand name (EN) must use Latin characters.",
        )
    return value


def validate_brand_name_ar(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not 1 <= len(value) <= 80:
        return ValidationError(
            code="invalid_brand_name_ar",
            message="Brand name (AR) must be between 1 and 80 characters.",
        )
    if not ARABIC_RE.search(value):
        return ValidationError(
            code="invalid_brand_name_ar",
            message="Brand name (AR) must contain Arabic script.",
        )
    return value


def validate_master_id(
    raw: str,
    *,
    kind: str,
    master: MasterData,
    code: str,
    label: str,
) -> str | ValidationError:
    value = raw.strip() if isinstance(raw, str) else str(raw)
    if value not in master.ids_for_kind(kind):
        return ValidationError(code=code, message=f"Unknown {label}.")
    if kind == "unit_types" and value not in get_policy().product_lines:
        return ValidationError(code=code, message=f"Unknown {label}.")
    return value


def validate_malls(raw: list[str] | str, master: MasterData) -> list[str] | ValidationError:
    if isinstance(raw, str):
        return ValidationError(code="invalid_malls", message="Malls must be a list of mall ids.")
    if len(raw) < 1:
        return ValidationError(code="invalid_malls", message="Select a mall.")
    max_malls = get_policy().max_malls_per_inquiry
    if len(set(raw)) > max_malls:
        if max_malls == 1:
            return ValidationError(
                code="one_mall_per_inquiry",
                message=(
                    "Choose one mall per inquiry. Another inquiry can be raised for a second mall."
                ),
            )
        return ValidationError(
            code="too_many_malls",
            message=(
                f"Choose up to {max_malls} malls per inquiry. "
                "Another inquiry can be raised for the others."
            ),
        )
    raw = list(dict.fromkeys(raw))
    mall_ids = master.mall_ids()
    invalid = [mall_id for mall_id in raw if mall_id not in mall_ids]
    if invalid:
        return ValidationError(code="invalid_malls", message="One or more malls are not valid.")
    return list(raw)


def validate_area_min(raw: int | str) -> int | ValidationError:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return ValidationError(code="invalid_area_min", message="Area min must be a whole number.")
    if not 10 <= value <= 25000:
        return ValidationError(
            code="invalid_area_min",
            message="Area min must be between 10 and 25,000 sqm.",
        )
    return value


def validate_area_max(raw: int | str) -> int | ValidationError:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return ValidationError(code="invalid_area_max", message="Area max must be a whole number.")
    if not 10 <= value <= 25000:
        return ValidationError(
            code="invalid_area_max",
            message="Area max must be between 10 and 25,000 sqm.",
        )
    return value


def validate_area_range(area_min: int | None, area_max: int | None) -> ValidationError | None:
    if area_min is None or area_max is None:
        return None
    if area_min > area_max:
        return ValidationError(
            code="invalid_area_range",
            message="Area min cannot be greater than area max.",
        )
    return None


def validate_rent_min(raw: int | str) -> int | ValidationError:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return ValidationError(code="invalid_rent_min", message="Rent min must be a whole number.")
    if value < 0:
        return ValidationError(code="invalid_rent_min", message="Rent min cannot be negative.")
    return value


def validate_rent_max(raw: int | str) -> int | ValidationError:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return ValidationError(code="invalid_rent_max", message="Rent max must be a whole number.")
    if value < 0:
        return ValidationError(code="invalid_rent_max", message="Rent max cannot be negative.")
    return value


def validate_rent_range(rent_min: int | None, rent_max: int | None) -> ValidationError | None:
    if rent_min is None or rent_max is None:
        return None
    if rent_min > rent_max:
        return ValidationError(
            code="invalid_rent_range",
            message="Rent min cannot be greater than rent max.",
        )
    return None


def validate_rent_period_required(
    rent_period: str | None,
    rent_min: int | None,
    rent_max: int | None,
) -> ValidationError | None:
    if rent_min is None and rent_max is None:
        return None
    if not rent_period:
        return ValidationError(
            code="missing_rent_period",
            message="Rent period is required when rent is provided.",
        )
    return None


def validate_name(raw: str, *, code: str, label: str) -> str | ValidationError:
    value = raw.strip()
    if not 1 <= len(value) <= 50:
        return ValidationError(
            code=code,
            message=f"{label} must be between 1 and 50 characters.",
        )
    return value


def validate_email(raw: str) -> str | ValidationError:
    value = raw.strip()
    try:
        normalised = str(_EMAIL_ADAPTER.validate_python(value))
    except Exception:
        return ValidationError(code="invalid_email", message="Enter a valid email address.")
    return normalised


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw)


SAUDI_COUNTRY_CODE = "966"
# E.164: up to 15 digits including the country code, which never starts with 0.
_E164_DIGITS_RE = re.compile(r"^[1-9]\d{7,14}$")


def international_number(raw: str) -> str | ValidationError | None:
    """Normalise a non-Saudi number written in international form (+CC… or 00CC…).

    Returns None when the number is Saudi or written in local form, so the Saudi rules
    apply. Without a numbering-plan library we can't tell a foreign mobile from a
    foreign landline; the field it is written to decides.
    """
    stripped = raw.strip()
    if stripped.startswith("+"):
        digits = _digits_only(stripped)
    elif stripped.startswith("00"):
        digits = _digits_only(stripped)[2:]
    else:
        return None
    if digits.startswith(SAUDI_COUNTRY_CODE):
        return None
    if not _E164_DIGITS_RE.match(digits):
        return ValidationError(
            code="invalid_phone",
            message="Enter the number with its country code, e.g. +971501234567.",
        )
    if not get_policy().phone.allows(digits):
        return ValidationError(
            code="phone_country_not_allowed",
            message="We can only accept phone numbers from the supported countries.",
        )
    return f"+{digits}"


def normalise_mobile(raw: str) -> str | ValidationError:
    """Saudi mobiles (+9665…) or any international number with a country code."""
    international = international_number(raw)
    if international is not None:
        return international
    return normalise_saudi_mobile(raw)


def normalise_landline(raw: str) -> str | ValidationError:
    """Saudi landlines (+966 + 8 or 9 digits, not 5…) or any international number."""
    international = international_number(raw)
    if international is not None:
        return international
    return normalise_saudi_landline(raw)


def normalise_saudi_mobile(raw: str) -> str | ValidationError:
    digits = _digits_only(raw)
    if digits.startswith("966"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not re.match(r"^5\d{8}$", digits):
        return ValidationError(
            code="invalid_mobile",
            message=(
                "Mobile must be a Saudi number starting with 5 (e.g. +966501234567) "
                "or include its country code."
            ),
        )
    return f"+966{digits}"


def normalise_saudi_landline(raw: str) -> str | ValidationError:
    digits = _digits_only(raw)
    if digits.startswith("966"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not re.match(r"^[1-49]\d{7,8}$", digits):
        return ValidationError(
            code="invalid_landline",
            message=(
                "Landline must be +966 followed by 8 or 9 digits not starting with 5, "
                "or include its country code."
            ),
        )
    return f"+966{digits}"


def classify_contact_number(
    raw: str,
) -> tuple[Literal["mobile", "landline"], str] | ValidationError:
    """Decide mobile vs landline. Saudi numbers by prefix; other countries default to mobile."""
    international = international_number(raw)
    if isinstance(international, ValidationError):
        return international
    if international is not None:
        return ("mobile", international)
    digits = _digits_only(raw)
    if digits.startswith("966"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    if digits.startswith("5"):
        mobile = normalise_saudi_mobile(raw)
        if isinstance(mobile, ValidationError):
            return mobile
        return ("mobile", mobile)
    landline = normalise_saudi_landline(raw)
    if isinstance(landline, ValidationError):
        return landline
    return ("landline", landline)


def validate_vat_number(raw: str) -> str | ValidationError:
    value = _digits_only(raw)
    if not VAT_RE.match(value):
        return ValidationError(
            code="invalid_vat_number",
            message="VAT number must be 15 digits starting and ending with 3.",
        )
    return value


def validate_national_id_number(raw: str) -> str | ValidationError:
    value = _digits_only(raw)
    if not NATIONAL_ID_RE.match(value):
        return ValidationError(
            code="invalid_national_id",
            message="National ID / Iqama must be 10 digits starting with 1 or 2.",
        )
    return value


def validate_national_address(raw: str) -> str | ValidationError:
    value = raw.strip()
    if not 5 <= len(value) <= 250:
        return ValidationError(
            code="invalid_national_address",
            message="National address must be between 5 and 250 characters.",
        )
    return value


def validate_document_extension(file_name: str) -> ValidationError | None:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        return ValidationError(
            code="invalid_extension",
            message="File type not allowed. Use PDF, image, Word, Excel or ZIP.",
        )
    return None


def validate_document_size(size_bytes: int, max_bytes: int) -> ValidationError | None:
    if size_bytes > max_bytes:
        return ValidationError(
            code="too_large",
            message=f"File must be {max_bytes // (1024 * 1024)} MB or smaller.",
        )
    return None
