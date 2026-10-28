"""Additional tenant contacts (L4 §3.1, §3.5; requirements §7.1.1 c).

Deterministic helpers for the case agent's `update_contacts` tool and the
`submit_contacts` action: validation reuses the intake validators (Arabic digits
included); "that's me" copies the primary contact as `verified`, unconfirmed (golden
rule 2); typed values are `user`, confirmed.
"""

from __future__ import annotations

from typing import Any, cast

from app.domain import validation as v
from app.domain.models import FieldKey, FieldValue, InquiryDraft, Source
from app.policy.config import get_policy
from app.workflow.models import CONTACT_ROLE_LABELS, ContactRole, TenantContact

NAME_FIELDS = ("first_name", "last_name", "email", "mobile", "landline")


def _copy_primary(primary: InquiryDraft, role: str) -> TenantContact:
    def verified(key: FieldKey) -> FieldValue:
        value = primary.fields[key].value
        if value in (None, ""):
            return FieldValue()
        return FieldValue(value=value, source=Source.VERIFIED, confirmed=False)

    return TenantContact(
        role=cast(ContactRole, role),
        first_name=verified(FieldKey.FIRST_NAME),
        last_name=verified(FieldKey.LAST_NAME),
        email=verified(FieldKey.EMAIL),
        mobile=verified(FieldKey.MOBILE),
        landline=verified(FieldKey.LANDLINE),
        same_as_primary=True,
    )


def _put(contact: TenantContact, name: str, value: Any, source: Source) -> None:
    setattr(contact, name, FieldValue(value=value, source=source, confirmed=source == Source.USER))


def write_contacts(
    current: list[TenantContact],
    entries: list[dict[str, Any]],
    primary: InquiryDraft,
) -> tuple[list[TenantContact], dict[str, str]]:
    """Apply entries `{role, first_name?, last_name?, email?, contact_number?,
    same_as_primary?, source?}`. Returns the contacts and errors keyed `role.field`."""
    contacts = {c.role: c.model_copy(deep=True) for c in current}
    errors: dict[str, str] = {}
    for entry in entries:
        role = str(entry.get("role", ""))
        if role not in CONTACT_ROLE_LABELS:
            errors[f"{role}.role"] = "Unknown contact role."
            continue
        if entry.get("same_as_primary"):
            contacts[cast(ContactRole, role)] = _copy_primary(primary, role)
            continue
        source = Source.DERIVED if entry.get("source") == "derived" else Source.USER
        typed_role = cast(ContactRole, role)
        contact = contacts.get(typed_role) or TenantContact(role=typed_role)
        contact.same_as_primary = False

        for name in ("first_name", "last_name"):
            raw = entry.get(name)
            if raw is None or str(raw).strip() == "":
                continue
            checked = v.validate_name(
                str(raw), code=f"invalid_{name}", label=name.replace("_", " ")
            )
            if isinstance(checked, v.ValidationError):
                errors[f"{role}.{name}"] = checked.message
            else:
                _put(contact, name, checked, source)
        if entry.get("email"):
            checked_email = v.validate_email(str(entry["email"]))
            if isinstance(checked_email, v.ValidationError):
                errors[f"{role}.email"] = checked_email.message
            else:
                _put(contact, "email", checked_email, source)
        if entry.get("contact_number"):
            classified = v.classify_contact_number(str(entry["contact_number"]))
            if isinstance(classified, v.ValidationError):
                errors[f"{role}.contact_number"] = classified.message
            else:
                kind, number = classified
                _put(contact, kind, number, source)
        contacts[typed_role] = contact
    order = list(CONTACT_ROLE_LABELS)
    return sorted(contacts.values(), key=lambda c: order.index(c.role)), errors


def confirm_contacts(contacts: list[TenantContact]) -> list[TenantContact]:
    """The applicant accepted the contacts card: every value confirmed."""
    updated: list[TenantContact] = []
    for contact in contacts:
        copy = contact.model_copy(deep=True)
        for name in NAME_FIELDS:
            field = getattr(copy, name)
            if field.value not in (None, ""):
                field.confirmed = True
        updated.append(copy)
    return updated


def contacts_blockers(contacts: list[TenantContact]) -> list[str]:
    """What stops `submit_contacts`: missing required roles, incomplete or unconfirmed."""
    blockers: list[str] = []
    by_role = {c.role: c for c in contacts}
    for role in get_policy().second_level_contacts.required:
        if role not in by_role:
            blockers.append(f"missing_contact:{role}")
    for contact in contacts:
        if not (contact.first_name.value and contact.last_name.value and contact.email.value):
            blockers.append(f"incomplete_contact:{contact.role}")
        elif not (contact.mobile.value or contact.landline.value):
            blockers.append(f"incomplete_contact:{contact.role}")
        if any(
            getattr(contact, n).value not in (None, "") and not getattr(contact, n).confirmed
            for n in NAME_FIELDS
        ):
            blockers.append(f"unconfirmed_contact:{contact.role}")
    return blockers
