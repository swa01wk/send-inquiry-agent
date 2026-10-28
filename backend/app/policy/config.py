"""Business-rule policy: one validated file, read by code and rendered into the prompt.

This module must not import `app.domain` at load time: the domain validators import it.

See docs/specs/l3-reliable-intake.md §3.7. `load_policy` validates a file; `install_policy`
makes it the active policy (done once in `create_app`); `get_policy` reads the active one.
Tests swap policies with `use_policy`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "policy.yaml"

SAUDI_CALLING_CODE = "966"


class PolicyError(RuntimeError):
    """The policy file is missing or invalid. The app must not start."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PhonePolicy(_Strict):
    allowed_countries: Literal["any"] | list[str] = "any"

    @field_validator("allowed_countries")
    @classmethod
    def _calling_codes(cls, value: Literal["any"] | list[str]) -> Literal["any"] | list[str]:
        if value == "any":
            return value
        codes: list[str] = []
        for raw in value:
            code = str(raw).strip().lstrip("+")
            if not code.isdigit() or not 1 <= len(code) <= 3:
                msg = f"phone.allowed_countries: {raw!r} is not a calling code like '971'"
                raise ValueError(msg)
            codes.append(code)
        if not codes:
            msg = "phone.allowed_countries: use 'any' or list at least one calling code"
            raise ValueError(msg)
        return codes

    def allows(self, e164_digits: str) -> bool:
        """True if a number (digits after '+') is from an allowed country."""
        if e164_digits.startswith(SAUDI_CALLING_CODE) or self.allowed_countries == "any":
            return True
        return any(e164_digits.startswith(code) for code in self.allowed_countries)


class VerificationPolicy(_Strict):
    # The POC supports exactly these channels (POC assumption 1).
    email: Literal["link"] = "link"
    mobile: Literal["otp"] = "otp"


class ResendPolicy(_Strict):
    cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    max_per_hour: int = Field(default=5, ge=1, le=60)


class DocumentsPolicy(_Strict):
    # Document type ids (app.domain.models.DocType values).
    required: list[str]
    optional: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _each_type_once(self) -> DocumentsPolicy:
        # Local import: avoids an import cycle with app.domain.
        from app.domain.models import NON_INTAKE_DOC_TYPES, DocType

        known = {d.value for d in DocType if d not in NON_INTAKE_DOC_TYPES}
        listed = [*self.required, *self.optional]
        unknown = sorted({d for d in listed if d not in known})
        if unknown:
            msg = f"documents: unknown document types: {', '.join(unknown)}"
            raise ValueError(msg)
        duplicates = sorted({d for d in listed if listed.count(d) > 1})
        if duplicates:
            msg = f"documents: listed more than once: {', '.join(duplicates)}"
            raise ValueError(msg)
        missing = sorted(d for d in known if d not in listed)
        if missing:
            msg = (
                "documents: every document type must be required or optional; "
                f"missing {', '.join(missing)}"
            )
            raise ValueError(msg)
        return self

    def is_required(self, doc_type: str) -> bool:
        return str(doc_type) in self.required


ReviewRoleName = Literal["rlm_store", "rplm_media", "rplm_specialty"]
ContactRoleName = Literal[
    "authorized_signatory",
    "billing_contact",
    "leasing_manager",
    "financial_controller",
    "company_admin",
]


class SecondLevelContacts(_Strict):
    required: list[ContactRoleName] = Field(
        default_factory=lambda: ["authorized_signatory", "billing_contact"]
    )
    optional: list[ContactRoleName] = Field(
        default_factory=lambda: ["leasing_manager", "financial_controller", "company_admin"]
    )

    @model_validator(mode="after")
    def _each_role_once(self) -> SecondLevelContacts:
        listed = [*self.required, *self.optional]
        if len(set(listed)) != len(listed):
            msg = "second_level_contacts: each role once"
            raise ValueError(msg)
        return self


class PolicyConfig(_Strict):
    product_lines: list[str] = Field(min_length=1)
    existing_tenant_policy: Literal["sign_in", "allow_inquiry"] = "sign_in"
    max_malls_per_inquiry: int = Field(default=1, ge=1, le=10)
    phone: PhonePolicy = PhonePolicy()
    verification: VerificationPolicy = VerificationPolicy()
    resend: ResendPolicy = ResendPolicy()
    documents: DocumentsPolicy
    duplicate_policy: Literal["warn", "block"] = "warn"
    follow_on_reuse_hours: int = Field(default=24, ge=0, le=24 * 30)
    # ---- Review lifecycle (L4) ---------------------------------------------------------
    # Product line → reviewer role; the queue's region is the mall's region.
    review_routing: dict[str, ReviewRoleName] = Field(
        default_factory=lambda: {
            "store": "rlm_store",
            "media": "rplm_media",
            "specialty": "rplm_specialty",
        }
    )
    second_level_contacts: SecondLevelContacts = SecondLevelContacts()
    rejection_categories: list[str] = Field(
        default_factory=lambda: ["incomplete_documents", "not_a_fit", "no_space", "other"]
    )
    after_rejection: str = (
        "You can raise a new inquiry at any time, for example with updated documents or "
        "for another mall."
    )
    require_contacts_before_approval: bool = True
    auto_request_contacts_after_first_approval: bool = True

    @field_validator("product_lines")
    @classmethod
    def _unique_lines(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            msg = "product_lines: each product line once"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _every_line_routed(self) -> PolicyConfig:
        unrouted = sorted(set(self.product_lines) - set(self.review_routing))
        if unrouted:
            msg = f"review_routing: no reviewer role for {', '.join(unrouted)}"
            raise ValueError(msg)
        return self

    def with_changes(self, **changes: Any) -> PolicyConfig:
        """A validated copy with some values changed (tests and tooling)."""
        data = self.model_dump(mode="json")
        for key, value in changes.items():
            if isinstance(value, BaseModel):
                value = value.model_dump(mode="json")
            data[key] = value
        return PolicyConfig.model_validate(data)


def load_policy(path: str | Path | None = None) -> PolicyConfig:
    """Read and validate a policy file. Raises PolicyError with a readable message."""
    policy_path = Path(path) if path else DEFAULT_POLICY_PATH
    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        msg = f"Policy file not found: {policy_path} (set POLICY_PATH or restore the default)"
        raise PolicyError(msg) from exc
    except yaml.YAMLError as exc:
        msg = f"Policy file {policy_path} is not valid YAML: {exc}"
        raise PolicyError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"Policy file {policy_path} must be a mapping of rule names to values"
        raise PolicyError(msg)
    try:
        return PolicyConfig.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(file)'}: {err['msg']}"
            for err in exc.errors()
        )
        msg = f"Policy file {policy_path} is invalid: {problems}"
        raise PolicyError(msg) from exc


_active: PolicyConfig | None = None


def install_policy(policy: PolicyConfig) -> None:
    """Make this the active policy (create_app does this once at start-up)."""
    global _active
    _active = policy


def get_policy() -> PolicyConfig:
    """The active policy; the packaged default if nothing was installed yet."""
    global _active
    if _active is None:
        _active = load_policy()
    return _active


@contextmanager
def use_policy(policy: PolicyConfig) -> Iterator[PolicyConfig]:
    """Swap the active policy for the duration of a block (tests)."""
    global _active
    previous = _active
    _active = policy
    try:
        yield policy
    finally:
        _active = previous
