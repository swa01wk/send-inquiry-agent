"""Field and document validation."""

from __future__ import annotations

import re
from typing import Literal, TypeVar

from pydantic import BaseModel, EmailStr, TypeAdapter

from app.domain.master import MasterData
from app.policy.config import get_policy

T = TypeVar("T")

_EMAIL_ADAPTER: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)

CR_NUMBER_RE = re.compile(r"^[0-9]{10}$")
VAT_RE = re.compile(r"^3\d{13}3$")
NATIONAL_ID_RE = re.compile(r"^[12]\d{9}$")
LATIN_RE = re.compile(r"^[A-Za-z0-9\s&'.,\-()]+$")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
ALLOWED_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "doc", "docx", "xlsx", "zip"})


# Arabic-Indic (٠–٩) and Eastern Arabic-Indic (۰–۹) digits → ASCII (L3 §3.10).
_DIGIT_MAP = {
    **{0x0660 + i: ord("0") + i for i in range(10)},
    **{0x06F0 + i: ord("0") + i for i in range(10)},
}


def normalise_digits(text: str) -> str:
    """Arabic-Indic and Eastern Arabic-Indic digits as ASCII; everything else unchanged.

    Every numeric rule runs on the result (CR, phone numbers, VAT, National ID, area, rent)
    so an Arabic-speaking user gets the same checks as everyone else.
    """
    return text.translate(_DIGIT_MAP)


# How people write an area or a rent: "250,000", "250k", "30 sqm", "about 30",
# "up to 250,000 SAR per year". Only the number is kept; the period is a separate field.
_NUMBER_TEXT_RE = re.compile(
    r"(?:about|around|approx(?:imately)?\.?|roughly|~|up to|max(?:imum)?|at most|min(?:imum)?)?"
    r"\s*(?:sar|sr)?\s*(\d[\d,\u066c]*(?:\.\d+)?)\s*(k|thousand)?"
    r"\s*(?:sqm|sq\.?\s*m|m2|m\u00b2|square\s+met(?:er|re)s?|sar|sr|riyals?)?"
    r"(?:\s*(?:per|a|an|/)\s*(?:year|annum|month|yr|mo))?\.?",
    re.IGNORECASE,
)


def _normalised_number(raw: int | str) -> int | str:
    """A whole number from a plain number or the way people write one; else the text."""
    if not isinstance(raw, str):
        return raw
    text = normalise_digits(raw).strip()
    match = _NUMBER_TEXT_RE.fullmatch(text)
    if match is None:
        return text
    number = float(match.group(1).replace(",", "").replace("\u066c", ""))
    if match.group(2):
        number *= 1000
    return int(number) if number.is_integer() else text


class ValidationError(BaseModel):
    code: str
    message: str


def is_validation_error(result: T | ValidationError) -> bool:
    return isinstance(result, ValidationError)


def validate_cr_number(raw: str) -> str | ValidationError:
    value = normalise_digits(raw).strip()
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


_PERIOD_KINDS = frozenset({"lease_periods", "rent_periods"})
_RENT_PERIOD_WORDS = {
    "yearly": ("year", "yearly", "annual", "annually", "per year", "a year", "per annum", "pa"),
    "monthly": ("month", "monthly", "per month", "a month", "pm"),
}
_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
_LEASE_YEARS_RE = re.compile(r"^(\d+|one|two|three|four|five)(?:[\s-]*(?:years?|yrs?|y))?$")
_LEASE_MONTHS_RE = re.compile(r"^(\d+)[\s-]*(?:months?|mos?)$")


def _id_from_label(raw: str, kind: str, master: MasterData) -> str | None:
    """The seeded id whose id or English label matches, ignoring case; else None."""
    text = normalise_digits(raw).strip().casefold()
    for item_id in master.ids_for_kind(kind):
        if text in (item_id.casefold(), (master.label_for(kind, item_id) or "").casefold()):
            return item_id
    return None


def _period_id(raw: str, kind: str, master: MasterData) -> str | None:
    """Lease or rent period id from its label or the way people say it ("3 years",
    "per year"); None when it doesn't match one seeded period."""
    text = normalise_digits(raw).strip().casefold().strip(".")
    for item_id in master.ids_for_kind(kind):
        labels = {item_id.casefold(), (master.label_for(kind, item_id) or "").casefold()}
        if text in labels:
            return item_id
    if kind == "rent_periods":
        for item_id, words in _RENT_PERIOD_WORDS.items():
            if text.lstrip("/ ") in words:
                return item_id
        return None
    text = text.removesuffix(" lease").strip()
    months = _LEASE_MONTHS_RE.match(text)
    if months is not None:
        count = int(months.group(1))
        return f"{count // 12}y" if count and count % 12 == 0 else None
    match = _LEASE_YEARS_RE.match(text)
    if match is None:
        return None
    years = _NUMBER_WORDS.get(match.group(1), match.group(1))
    return f"{years}y"


_RANGE_RE = re.compile(
    r"(\d[\d,\u066c]*(?:\.\d+)?\s*k?)\s*(?:-|\u2013|\u2014|to|and)\s*(\d[\d,\u066c]*(?:\.\d+)?\s*k?)",
    re.IGNORECASE,
)
_FIRST_NUMBER_RE = re.compile(r"\d[\d,\u066c]*(?:\.\d+)?\s*k?", re.IGNORECASE)
_RENT_FLOOR_RE = re.compile(r"\b(?:from|at least|min(?:imum)?|starting)\b", re.IGNORECASE)


def split_amount(raw: object) -> tuple[object, object] | None:
    """`(low, high)` from "25-35 sqm", "between 200k and 250k", or `(n, n)` from one
    value ("30 sqm", 250000). None when there's no number. Each side still goes through
    the field's own validator."""
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return raw, raw
    if not isinstance(raw, str):
        return None
    text = normalise_digits(raw)
    if (pair := _RANGE_RE.search(text)) is not None:
        low, high = pair.group(1).strip(), pair.group(2).strip()
        if high.lower().endswith("k") and not low.lower().endswith("k"):
            low = f"{low}k"  # "200-250k" means 200k to 250k
        return low, high
    if (single := _FIRST_NUMBER_RE.search(text)) is None:
        return None
    return single.group(0).strip(), single.group(0).strip()


def rent_is_floor(raw: object) -> bool:
    """ "from 200k", "at least 200k": a one-sided rent is a minimum, otherwise a budget cap."""
    return isinstance(raw, str) and _RENT_FLOOR_RE.search(raw) is not None


def rent_period_in(raw: object) -> str | None:
    """ "per year" / "a month" inside a rent value; the period id or None."""
    if not isinstance(raw, str):
        return None
    text = raw.casefold()
    if re.search(r"\b(?:year|yearly|annual|annually|annum|yr)\b", text):
        return "yearly"
    if re.search(r"\b(?:month|monthly|mo)\b", text):
        return "monthly"
    return None


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
        # The label instead of the id ("Store", "Specialty"): seen in live eval, 2 Nov.
        value = _id_from_label(value, kind, master) or value
    if value not in master.ids_for_kind(kind) and kind in _PERIOD_KINDS:
        value = _period_id(value, kind, master) or value
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
        value = int(_normalised_number(raw))
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
        value = int(_normalised_number(raw))
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
        value = int(_normalised_number(raw))
    except (TypeError, ValueError):
        return ValidationError(code="invalid_rent_min", message="Rent min must be a whole number.")
    if value < 0:
        return ValidationError(code="invalid_rent_min", message="Rent min cannot be negative.")
    return value


def validate_rent_max(raw: int | str) -> int | ValidationError:
    try:
        value = int(_normalised_number(raw))
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
    return re.sub(r"[^0-9]", "", normalise_digits(raw))


SAUDI_COUNTRY_CODE = "966"
# E.164: up to 15 digits including the country code, which never starts with 0.
_E164_DIGITS_RE = re.compile(r"^[1-9]\d{7,14}$")


def international_number(raw: str) -> str | ValidationError | None:
    """Normalise a non-Saudi number written in international form (+CC… or 00CC…).

    Returns None when the number is Saudi or written in local form, so the Saudi rules
    apply. Without a numbering-plan library we can't tell a foreign mobile from a
    foreign landline; the field it is written to decides.
    """
    stripped = normalise_digits(raw).strip()
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
