"""Additional tenant contacts (L4 §3.5): validation, "that's me", required roles."""

from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import Source
from app.workflow.contacts import confirm_contacts, contacts_blockers, write_contacts


def _primary():
    draft, _w, errors = write_fields(
        new_inquiry_draft(),
        [
            ("first_name", "Sara", Source.USER),
            ("last_name", "Ali", Source.USER),
            ("email", "sara@beanstreet.example", Source.USER),
            ("contact_number", "0501234567", Source.USER),
        ],
        master=load_master_data(),
    )
    assert not errors
    return draft


def test_thats_me_copies_the_primary_contact_unconfirmed() -> None:
    contacts, errors = write_contacts(
        [], [{"role": "authorized_signatory", "same_as_primary": True}], _primary()
    )
    assert errors == {}
    signatory = contacts[0]
    assert signatory.same_as_primary
    assert signatory.email.value == "sara@beanstreet.example"
    assert signatory.email.source == Source.VERIFIED and signatory.email.confirmed is False
    assert "unconfirmed_contact:authorized_signatory" in contacts_blockers(contacts)
    assert "unconfirmed_contact:authorized_signatory" not in contacts_blockers(
        confirm_contacts(contacts)
    )


def test_typed_contact_with_arabic_digits() -> None:
    contacts, errors = write_contacts(
        [],
        [
            {
                "role": "billing_contact",
                "first_name": "Omar",
                "last_name": "Saleh",
                "email": "omar@beanstreet.example",
                "contact_number": "٠٥٥١٢٣٤٥٦٧",
            }
        ],
        _primary(),
    )
    assert errors == {}
    billing = contacts[0]
    assert billing.mobile.value == "+966551234567"
    assert billing.first_name.source == Source.USER and billing.first_name.confirmed


def test_field_errors_and_unknown_roles() -> None:
    contacts, errors = write_contacts(
        [],
        [
            {"role": "billing_contact", "email": "not-an-email", "contact_number": "12"},
            {"role": "ceo", "first_name": "X"},
        ],
        _primary(),
    )
    assert set(errors) == {"billing_contact.email", "billing_contact.contact_number", "ceo.role"}


def test_required_roles_from_the_policy() -> None:
    contacts, _ = write_contacts(
        [], [{"role": "authorized_signatory", "same_as_primary": True}], _primary()
    )
    blockers = contacts_blockers(confirm_contacts(contacts))
    assert blockers == ["missing_contact:billing_contact"]


def test_contacts_keep_role_order() -> None:
    contacts, _ = write_contacts(
        [],
        [
            {"role": "company_admin", "same_as_primary": True},
            {"role": "authorized_signatory", "same_as_primary": True},
        ],
        _primary(),
    )
    assert [c.role for c in contacts] == ["authorized_signatory", "company_admin"]
