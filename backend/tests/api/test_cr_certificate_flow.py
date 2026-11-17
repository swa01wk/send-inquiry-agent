"""M1 and M2 (decided 16–17 Nov, docs/assumptions.md) on the flow v2 Company Registration card.

M1: the CR certificate is optional everywhere. On the card it can stand in for typing the CR
(S2, S4, S15): the document review service reads the number and the card checks it like a
typed one, so it never reaches the model. Uploaded later (the documents step, or the
call-centre application link), a certificate whose number differs from the inquiry's CR is
flagged and never blocks.

M2: a registered CR whose person has no Tenant Central login may press "I don't have a
login" and raise the inquiry as new, flagged for the Leasing Admin (policy
`registered_cr_without_login: continue`).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.agent.model import ScriptedChatModel
from app.domain.case_brief import build_case_brief
from app.domain.document_checks import document_mismatches
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey
from app.policy.config import get_policy, use_policy
from app.store.models import Inquiry, InquiryStatus
from app.store.session_bridge import apply_session_to_inquiry
from app.workflow.models import Case, CaseStatus
from httpx import AsyncClient
from tests.scenarios.helpers import chat_action, token_text, ui_cards, upload_document

pytestmark = pytest.mark.intake_v2

PDF = b"%PDF-1.4 test"
NEW_CR = "1010123456"
REGISTERED_CR = "1010000000"


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Thanks, let's carry on."}] * 8)


async def _session(client: AsyncClient) -> str:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    return created.json()["session_id"]


async def _upload_certificate(client: AsyncClient, session_id: str, name: str) -> dict:
    uploaded = await upload_document(client, session_id, "cr_certificate", name, PDF)
    assert uploaded["status_code"] == 200, uploaded["body"]
    return uploaded["body"]


# ---- M1: the certificate instead of typing -------------------------------------------------


async def test_certificate_on_the_card_is_checked_like_a_typed_cr(client: AsyncClient, app) -> None:
    """S2 with the certificate: not registered, the CR stays on the inquiry."""
    session_id = await _session(client)
    body = await _upload_certificate(client, session_id, "cr_certificate_new.pdf")
    card = body["card"]
    assert card["card_type"] == "company_registration"
    assert card["payload"]["certificate_name"] == "cr_certificate_new.pdf"
    assert card["payload"]["state"] == "open"
    session = await app.state.session_store.get(session_id)
    # Uploading alone checks nothing and writes no CR.
    assert session.draft.cr_status == "unknown"
    assert session.draft.fields[FieldKey.CR_NUMBER].value is None

    events = await chat_action(client, session_id, "cr_check", {"source": "certificate"})
    registration = ui_cards(events, "company_registration")[-1]["payload"]
    assert registration["state"] == "not_registered"
    assert registration["certificate_name"] == "cr_certificate_new.pdf"
    assert NEW_CR not in json.dumps(registration)
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "new"
    assert session.draft.fields[FieldKey.CR_NUMBER].value == NEW_CR
    assert DocType.CR_CERTIFICATE in session.draft.documents


async def test_unreadable_certificate_asks_to_type_it_quietly(client: AsyncClient, app) -> None:
    session_id = await _session(client)
    await _upload_certificate(client, session_id, "some_scan.pdf")
    events = await chat_action(client, session_id, "cr_check", {"source": "certificate"})
    registration = ui_cards(events, "company_registration")[-1]["payload"]
    assert registration["state"] == "open"
    assert "type the number" in registration["error"]
    assert token_text(events) == ""
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "unknown"


async def test_typing_still_works_and_the_certificate_stays_optional(
    client: AsyncClient, app
) -> None:
    session_id = await _session(client)
    events = await chat_action(client, session_id, "cr_check", {"cr_number": NEW_CR})
    payload = ui_cards(events, "company_registration")[-1]["payload"]
    assert payload["state"] == "not_registered"
    assert payload["upload_label"] == "Upload CR certificate"
    session = await app.state.session_store.get(session_id)
    assert DocType.CR_CERTIFICATE not in session.draft.documents
    # The certificate isn't a required document (M1: optional everywhere).
    assert DocType.CR_CERTIFICATE.value not in get_policy().documents.required


async def test_certificate_with_a_duplicate_cr_reaches_the_duplicate_check(
    client: AsyncClient, app
) -> None:
    """S15 with the certificate: its number is the inquiry's CR, so the open inquiry for the
    same CR and mall is found exactly as when the number is typed."""
    from app.workflow.duplicates import open_duplicate

    session_id = await _session(client)
    await _upload_certificate(client, session_id, "cr_certificate_duplicate.pdf")
    await chat_action(client, session_id, "cr_check", {"source": "certificate"})
    session = await app.state.session_store.get(session_id)
    assert session.draft.fields[FieldKey.CR_NUMBER].value == "1010222222"
    draft = session.draft.model_copy(deep=True)
    draft.fields[FieldKey.MALLS].value = ["riyadh-mall-a"]
    other = draft.model_copy(deep=True)
    other.reference = "GEO-STR-000201"
    case = Case(
        id="GEO-STR-000201",
        reference="GEO-STR-000201",
        session_id="sess-other",
        status=CaseStatus.FIRST_REVIEW,
        draft=other,
        submitted_at=datetime(2026, 11, 16, 9, tzinfo=UTC),
    )
    found = open_duplicate([case], draft)
    assert found is not None and found.reference == "GEO-STR-000201"


async def test_a_later_certificate_that_disagrees_is_flagged_not_blocking(
    client: AsyncClient, app
) -> None:
    """After a typed CR (S2) or the executive's CR (CC2, CC3), a certificate uploaded with
    the documents is compared with the inquiry's CR."""
    session_id = await _session(client)
    await chat_action(client, session_id, "cr_check", {"cr_number": NEW_CR})
    body = await _upload_certificate(client, session_id, "cr_certificate_mismatch.pdf")
    assert "cr_number" in body["mismatches"]
    # Not on the Company Registration card any more: the documents checklist answers.
    assert body["card"]["card_type"] != "company_registration"
    session = await app.state.session_store.get(session_id)
    mismatches = document_mismatches(session.draft, load_master_data())
    assert [m.field for m in mismatches] == ["cr_number"]
    assert session.draft.fields[FieldKey.CR_NUMBER].value == NEW_CR  # never overwritten


async def test_a_later_certificate_that_agrees_is_not_flagged(client: AsyncClient, app) -> None:
    session_id = await _session(client)
    await chat_action(client, session_id, "cr_check", {"cr_number": NEW_CR})
    body = await _upload_certificate(client, session_id, "cr_certificate_new.pdf")
    assert body["mismatches"] == []


# ---- M2: registered CR without a login --------------------------------------------------------


async def test_registered_cr_offers_i_dont_have_a_login(client: AsyncClient, app) -> None:
    session_id = await _session(client)
    events = await chat_action(client, session_id, "cr_check", {"cr_number": REGISTERED_CR})
    sign_in = ui_cards(events, "sign_in_prompt")[-1]["payload"]
    assert sign_in["no_login_label"] == "I don't have a login"
    assert sign_in["continued_without_login"] is False
    session = await app.state.session_store.get(session_id)
    assert session.closed == "redirected_to_sign_in"


async def test_continue_without_login_raises_the_inquiry_as_new(client: AsyncClient, app) -> None:
    session_id = await _session(client)
    await _upload_certificate(client, session_id, "cr_certificate_registered.pdf")
    await chat_action(client, session_id, "cr_check", {"source": "certificate"})
    events = await chat_action(client, session_id, "continue_without_login", {})
    sign_in = ui_cards(events, "sign_in_prompt")[-1]["payload"]
    assert sign_in["continued_without_login"] is True
    registration = ui_cards(events, "company_registration")[-1]["payload"]
    assert registration["state"] == "continued_no_login"
    assert token_text(events)  # the agent carries on with the next section
    session = await app.state.session_store.get(session_id)
    assert session.draft.cr_status == "new"
    assert session.draft.registered_no_login is True
    assert session.draft.fields[FieldKey.CR_NUMBER].value == REGISTERED_CR
    assert session.closed is None
    audit = [e["type"] for e in app.state.services.audit.events(session_id)]
    assert "inquiry_continued_without_login" in audit


async def test_continue_without_login_twice_is_refused_quietly(client: AsyncClient, app) -> None:
    session_id = await _session(client)
    await chat_action(client, session_id, "cr_check", {"cr_number": REGISTERED_CR})
    await chat_action(client, session_id, "continue_without_login", {})
    again = await chat_action(client, session_id, "continue_without_login", {})
    assert token_text(again) == ""


async def test_sign_in_only_policy_keeps_the_chart(client: AsyncClient, app) -> None:
    with use_policy(get_policy().with_changes(registered_cr_without_login="sign_in_only")):
        session_id = await _session(client)
        events = await chat_action(client, session_id, "cr_check", {"cr_number": REGISTERED_CR})
        sign_in = ui_cards(events, "sign_in_prompt")[-1]["payload"]
        assert sign_in["no_login_label"] is None
        refused = await chat_action(client, session_id, "continue_without_login", {})
        assert token_text(refused) == ""
        session = await app.state.session_store.get(session_id)
        assert session.draft.cr_status == "existing"
        assert session.draft.registered_no_login is False


def test_the_inquiry_reopens_once_they_continue() -> None:
    from app.domain.draft_ops import new_inquiry_draft
    from app.sessions import Session

    draft = new_inquiry_draft()
    draft.intake_flow = "v2"
    draft.cr_status = "new"
    draft.registered_no_login = True
    from uuid import uuid4

    now = datetime(2026, 11, 17, 9, tzinfo=UTC)
    session = Session(id="s1", draft=draft, created_at=now, last_seen=now)
    inquiry = Inquiry(
        id=uuid4(),
        status=InquiryStatus.REDIRECTED,
        draft=draft,
        created_at=now,
        updated_at=now,
        last_seen_at=now,
        expires_at=now,
    )
    assert apply_session_to_inquiry(session, inquiry).status == InquiryStatus.DRAFT


def test_the_leasing_admin_sees_the_flag() -> None:
    from app.domain.draft_ops import new_inquiry_draft

    draft = new_inquiry_draft()
    draft.intake_flow = "v2"
    draft.cr_status = "new"
    draft.registered_no_login = True
    draft.reference = "GEO-STR-000301"
    case = Case(
        id="GEO-STR-000301",
        reference="GEO-STR-000301",
        session_id="s",
        status=CaseStatus.FIRST_REVIEW,
        draft=draft,
        submitted_at=datetime(2026, 11, 17, 9, tzinfo=UTC),
    )
    brief = build_case_brief(case, load_master_data(), now=datetime(2026, 11, 17, 10, tzinfo=UTC))
    assert brief.cr_status == "registered, no login"
    assert any("contact without a login" in item for item in brief.next_decision_checklist)


def test_the_s4_continue_script_runs_the_v2_intake() -> None:
    from types import SimpleNamespace

    from app.agent.cr_question import flow_v2_intake_for

    session = SimpleNamespace(assisted=False, channel=None, test_scenario="qa-s4-continue")
    assert flow_v2_intake_for(session) is True
