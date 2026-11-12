"""Reject Lead revokes the first-approval Azure AD invitation (flow v2 §3.6, V9, FV3).

The tests run with one reviewer role doing both levels (`tests/conftest.py`), so
`STORE_CENTRAL` gives the first approval and then rejects the lead.
"""

from app.domain.models import FieldKey, InquiryDraft
from app.policy.config import get_policy, use_policy
from app.workflow.labels import LEAD_REJECTED, TENANT_NOT_QUALIFIED
from app.workflow.models import CaseStatus
from tests.lifecycle.conftest import APPLICANT, STORE_CENTRAL, act, outbox, submit_case

EXISTING_ACCOUNT = "layla.hassan@oasiscoffee.example"  # seeded in mock_world/identity.json


def _case(app, reference):
    return app.state.services.cases.get(reference)


def _audit_types(app, reference) -> list[str]:
    return [e["type"] for e in app.state.services.audit.events(reference)]


async def _qualify(client, reference) -> None:
    approved = await act(client, STORE_CENTRAL, reference, "approve_first")
    assert approved.status_code == 200, approved.text


async def _reject(client, reference, remarks: str = "No space in that size.") -> None:
    rejected = await act(
        client, STORE_CENTRAL, reference, "reject", remarks=remarks, reason_category="no_space"
    )
    assert rejected.status_code == 200, rejected.text


async def test_reject_lead_revokes_the_first_approval_invitation(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _qualify(client, reference)
    invitation = _case(app, reference).onboarding.invitations[0]
    assert invitation.role == "primary_contact"
    accept_link = outbox(app, APPLICANT, "azure_ad_invitation")[0]["links"][0]
    await client.get(accept_link.replace("http://localhost:8000", ""))
    identity = app.state.services.identity
    assert identity.has_account(APPLICANT)

    await _reject(client, reference)

    case = _case(app, reference)
    assert case.status == CaseStatus.REJECTED
    assert case.onboarding.invitations[0].revoked_at is not None
    assert not identity.has_account(APPLICANT)
    assert identity.accept(invitation.id) is None  # a revoked invitation can't be accepted
    assert "identity_revoked" in _audit_types(app, reference)
    mail = outbox(app, APPLICANT, "inquiry_rejected")
    assert len(mail) == 1 and f"Outcome: {LEAD_REJECTED}" in mail[0]["body"]


async def test_first_level_rejection_has_nothing_to_revoke(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _reject(client, reference, remarks="Not a fit.")
    case = _case(app, reference)
    assert case.onboarding.invitations == []
    assert "identity_revoked" not in _audit_types(app, reference)
    mail = outbox(app, APPLICANT, "inquiry_rejected")
    assert f"Outcome: {TENANT_NOT_QUALIFIED}" in mail[0]["body"]
    assert outbox(app, APPLICANT, "azure_ad_invitation") == []


async def test_an_existing_account_is_never_invited_or_revoked(life) -> None:
    """Assumption A1: an email that already has a login gets no second account."""
    client, app = life

    def existing_email(draft: InquiryDraft) -> None:
        draft.fields[FieldKey.EMAIL].value = EXISTING_ACCOUNT

    reference = await submit_case(client, app, prepare=existing_email)
    await _qualify(client, reference)
    assert _case(app, reference).onboarding.invitations == []
    await _reject(client, reference)
    assert app.state.services.identity.has_account(EXISTING_ACCOUNT)
    assert "identity_revoked" not in _audit_types(app, reference)


async def test_revoke_can_be_switched_off(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _qualify(client, reference)
    off = get_policy().with_changes(identity={"revoke_on_lead_rejection": False})
    with use_policy(off):
        await _reject(client, reference)
    assert _case(app, reference).onboarding.invitations[0].revoked_at is None
