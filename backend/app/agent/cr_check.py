"""Apply a CR registry answer to the draft (shared by the `verify_cr` tool and form mode)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain import draft_ops
from app.domain import validation as v
from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft, Source
from app.policy.config import get_policy
from app.services.cr import CrResult

CrKind = Literal["existing", "existing_allowed", "new"]
CONFIRMABLE_FROM_CR = (FieldKey.COMPANY_NAME.value, FieldKey.COMPANY_ADDRESS.value)


@dataclass
class CrOutcome:
    kind: CrKind
    draft: InquiryDraft
    changed: list[str]
    confirm_keys: list[str] = field(default_factory=list)
    errors: dict[str, v.ValidationError] = field(default_factory=dict)


def apply_cr_result(
    draft: InquiryDraft, cr_number: str, result: CrResult, master: MasterData
) -> CrOutcome:
    """Existing account → `existing` (or continue under `allow_inquiry`); new → prefill the
    company name and address as `verified`, unconfirmed, for the user to confirm."""
    if result.exists and get_policy().existing_tenant_policy == "allow_inquiry":
        # Requirements §7.1: existing tenants may raise an inquiry from this page.
        updated, written, _errors = draft_ops.write_fields(
            draft, [(FieldKey.CR_NUMBER.value, cr_number, Source.USER)], master=master
        )
        updated.cr_status = "new"
        return CrOutcome(kind="existing_allowed", draft=updated, changed=written)

    if result.exists:
        updated = draft.model_copy(deep=True)
        updated.cr_status = "existing"
        updated, written, _errors = draft_ops.write_fields(
            updated, [(FieldKey.CR_NUMBER.value, cr_number, Source.USER)], master=master
        )
        return CrOutcome(kind="existing", draft=updated, changed=["cr_number", *written])

    entries: list[tuple[str, object, Source]] = [
        (FieldKey.CR_NUMBER.value, cr_number, Source.USER),
    ]
    if result.company_name:
        entries.append((FieldKey.COMPANY_NAME.value, result.company_name, Source.VERIFIED))
    if result.company_address:
        entries.append((FieldKey.COMPANY_ADDRESS.value, result.company_address, Source.VERIFIED))
    updated, written, errors = draft_ops.write_fields(draft, entries, master=master)
    updated.cr_status = "new"
    confirm_keys = [k for k in written if k in CONFIRMABLE_FROM_CR]
    return CrOutcome(
        kind="new", draft=updated, changed=written, confirm_keys=confirm_keys, errors=errors
    )
