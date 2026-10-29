"""Intake channels (spec §15): staff writes, the call-centre console and application link,
the tenant record, existing-tenant mode on Tenant Central, and the public page."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from app.agent.channels import restamp_staff
from app.agent.graph import build_assisted_graph, build_graph
from app.agent.model import ScriptedChatModel
from app.agent.tools import ASSISTED_TOOLS
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source, new_inquiry_draft
from app.domain.rules import can_submit
from app.main import create_app
from app.policy.config import get_policy, use_policy
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.lifecycle.conftest import (
    STORE_CENTRAL,
    act,
    lifecycle_settings,
    outbox,
    token_from,
)
from tests.scenarios.helpers import chat_action, chat_message, ready_to_submit_draft, ui_cards

STAFF = "customer-care-1"
GUEST_SERVICE = "guest-service-1"
OASIS = "T-1001"  # one brand, CR 1010000000
AL_NOOR = "T-1002"  # two brands, CR 1010444444


@asynccontextmanager
async def channel_app(
    tmp_path: Path, steps: list[dict[str, Any]] | None = None
) -> AsyncIterator[tuple[AsyncClient, Any]]:
    """The app with every channel on and a scripted model playing `steps` in order."""
    settings = lifecycle_settings(tmp_path)
    model = ScriptedChatModel(steps=[*(steps or []), *([{"content": "OK"}] * 20)])

    def factory() -> ScriptedChatModel:
        return model

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    application.state.assisted_graph = build_assisted_graph(model_factory=factory)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as c:
        yield c, application


def tool_call(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    }


async def new_assisted(
    client: AsyncClient, staff: str = STAFF, *, scenario: str | None = None
) -> str:
    headers: dict[str, str] = {"X-Staff-Id": staff}
    if scenario:
        headers["X-Test-Scenario"] = scenario
    created = await client.post("/api/callcentre/inquiries", headers=headers)
    assert created.status_code == 200, created.text
    return str(created.json()["session_id"])


# ---- Staff source -------------------------------------------------------------------


def test_restamp_turns_this_turns_user_writes_into_staff() -> None:
    before = new_inquiry_draft()
    before.fields[FieldKey.COMPANY_NAME].value = "Kept Co"
    before.fields[FieldKey.COMPANY_NAME].source = Source.USER
    after = before.model_copy(deep=True)
    after.fields[FieldKey.BRAND_NAME_EN].value = "Bean Street"
    after.fields[FieldKey.BRAND_NAME_EN].source = Source.USER
    after.fields[FieldKey.SALES_CATEGORY].value = "fnb_cafe"
    after.fields[FieldKey.SALES_CATEGORY].source = Source.DERIVED
    restamped, changed = restamp_staff(before, after)
    assert changed == ["brand_name_en"]
    assert restamped.fields[FieldKey.BRAND_NAME_EN].source == Source.STAFF
    assert restamped.fields[FieldKey.BRAND_NAME_EN].confirmed is False
    assert restamped.fields[FieldKey.COMPANY_NAME].source == Source.USER  # unchanged
    assert restamped.fields[FieldKey.SALES_CATEGORY].source == Source.DERIVED


def test_staff_values_block_submit_until_confirmed() -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.COMPANY_NAME].value = "Acme"
    draft.fields[FieldKey.COMPANY_NAME].source = Source.STAFF
    tokens = {b.token for b in can_submit(draft)}
    assert "unconfirmed_field:company_name" in tokens


def test_assisted_allowlist() -> None:
    names = {t.name for t in ASSISTED_TOOLS}
    assert {"send_verification", "request_documents", "show_review"}.isdisjoint(names)
    assert {"update_draft", "verify_cr", "show_application_link"} <= names


# ---- Call-centre console --------------------------------------------------------------


async def test_console_needs_a_staff_sign_in_and_lists_staff(life) -> None:
    client, _app = life
    staff = (await client.get("/api/callcentre/staff")).json()
    assert {s["id"] for s in staff} == {STAFF, GUEST_SERVICE}
    assert (await client.post("/api/callcentre/inquiries")).status_code == 401
    reviewer = await client.post("/api/callcentre/inquiries", headers={"X-Staff-Id": STORE_CENTRAL})
    assert reviewer.status_code == 401  # reviewers aren't call-centre staff


async def test_what_the_executive_types_is_staff(tmp_path: Path) -> None:
    steps = [
        tool_call(
            "update_draft",
            {"fields": [{"key": "brand_name_en", "value": "Bean Street", "source": "user"}]},
            "a1",
        ),
        {"content": "Saved. What do they sell?"},
    ]
    async with channel_app(tmp_path, steps) as (client, app):
        session_id = await new_assisted(client)
        session = await app.state.session_store.get(session_id)
        assert session.channel == "assisted" and session.created_by == STAFF
        await chat_message(client, session_id, "The brand is Bean Street")
        brand = session.draft.fields[FieldKey.BRAND_NAME_EN]
        assert (brand.value, brand.source, brand.confirmed) == ("Bean Street", Source.STAFF, False)
        routed = [
            e
            for e in app.state.services.audit.events(session_id)
            if e["type"] == "routing_decision"
        ]
        assert routed == []  # staff chats skip the intent router


async def assisted_ready(client: AsyncClient, app: Any) -> tuple[str, Any]:
    session_id = await new_assisted(client)
    session = await app.state.session_store.get(session_id)
    draft = ready_to_submit_draft(app)
    draft.email_verified = draft.mobile_verified = False
    draft.documents = {}
    for key in FieldKey:  # as if the executive had typed everything
        field = draft.fields[key]
        if field.value not in (None, "", []) and field.source == Source.USER:
            draft.fields[key] = field.model_copy(
                update={"source": Source.STAFF, "confirmed": False}
            )
    session.draft = draft
    return session_id, session


async def test_application_link_hands_the_inquiry_to_the_applicant(life) -> None:
    client, app = life
    session_id, session = await assisted_ready(client, app)
    email = str(session.draft.fields[FieldKey.EMAIL].value)

    first = await chat_action(client, session_id, "send_application_link")
    assert ui_cards(first, "send_link")[0]["payload"]["sent_to_masked"]
    old_link = outbox(app, email, "complete_application")[0]["links"][0]
    await chat_action(client, session_id, "send_application_link")  # resend
    links = outbox(app, email, "complete_application")
    assert len(links) == 2
    new_link = links[0]["links"][0]
    assert "/inquiry/verify?t=" in new_link

    stale = await client.post("/api/verifications/email", json={"token": token_from(old_link)})
    assert stale.status_code == 400 and stale.json()["error"]["code"] == "token_used"

    opened = await client.post("/api/verifications/email", json={"token": token_from(new_link)})
    assert opened.status_code == 200, opened.text
    applicant_id = opened.json()["session_id"]
    assert applicant_id != session_id
    resumed = await client.post(
        "/api/sessions/resume", json={"token": opened.json()["resume_token"]}
    )
    body = resumed.json()
    assert "call centre started this inquiry" in body["messages"][-1]["text"]
    card = next(c for c in body["cards"] if c["card_type"] == "basic_info_review")
    assert any(r["source"] == "staff" and not r["confirmed"] for r in card["payload"]["rows"])
    applicant = await app.state.session_store.get(applicant_id)
    assert applicant.draft.email_verified is True
    assert (applicant.channel, applicant.created_by, applicant.staff_id) == (
        "assisted",
        STAFF,
        None,
    )
    assert (await app.state.session_store.get(session_id)).closed == "handed_to_applicant"

    again = await client.post("/api/verifications/email", json={"token": token_from(new_link)})
    assert again.json()["error"]["code"] == "token_used"

    proceeded = await chat_action(client, applicant_id, "proceed_basic_info")
    assert ui_cards(proceeded, "basic_info_review")[0]["payload"]["proceeded"] is True
    assert not [
        k
        for k in FieldKey
        if applicant.draft.fields[k].source == Source.STAFF
        and not applicant.draft.fields[k].confirmed
    ]


async def test_assisted_e2e_script_existing_cr_then_send_link(life) -> None:
    client, app = life
    session_id = await new_assisted(client, scenario="c1-existing-cr")
    events = await chat_message(
        client,
        session_id,
        "The caller gave CR 1010000000 for a specialty kiosk at Riyadh Mall A",
    )
    choice = ui_cards(events, "existing_cr_choice")[0]["payload"]
    assert choice["company_name"] == "Oasis Coffee Company"
    assert {o["value"] for o in choice["options"]} == {"sign_in", "continue"}
    continued = await chat_action(client, session_id, "existing_cr_choice", {"choice": "continue"})
    assert ui_cards(continued, "existing_cr_choice")[0]["payload"]["chosen"] == "continue"
    link_card = ui_cards(continued, "send_link")[-1]["payload"]
    assert link_card["can_send"] is True


async def test_call_centre_e2e_script_reaches_send_link(life) -> None:
    client, app = life
    session_id = await new_assisted(client, scenario="a2-call-centre")
    staff = await app.state.session_store.get(session_id)
    assert staff.test_scenario == "a2-call-centre"

    await chat_message(client, session_id, "Skip the CR for now")
    await chat_message(
        client,
        session_id,
        "Bean Street Trading Co., Olaya Street Riyadh — "
        "coffee kiosk at Riyadh Mall A, brand Bean Street",
    )
    events = await chat_message(
        client,
        session_id,
        "Sara Ali, sara@beanstreet.example, 0501234567",
    )
    link_card = ui_cards(events, "send_link")[-1]["payload"]
    assert link_card["can_send"] is True


async def test_application_link_e2e_script_on_applicant_session(life) -> None:
    client, app = life
    session_id = await new_assisted(client, scenario="a2-call-centre")
    await chat_message(client, session_id, "Skip the CR for now")
    await chat_message(
        client,
        session_id,
        "Bean Street Trading Co., Olaya Street — Bean Street coffee kiosk, Riyadh Mall A",
    )
    await chat_message(client, session_id, "Sara Ali, sara@beanstreet.example, 0501234567")
    email = "sara@beanstreet.example"
    await chat_action(client, session_id, "send_application_link")
    link = outbox(app, email, "complete_application")[0]["links"][0]
    opened = await client.post(
        "/api/verifications/email",
        json={"token": token_from(link)},
        headers={"X-Test-Scenario": "a2-applicant"},
    )
    assert opened.status_code == 200, opened.text
    applicant_id = opened.json()["session_id"]
    staff = await app.state.session_store.get(session_id)
    applicant = await app.state.session_store.get(applicant_id)
    assert staff.test_scenario == "a2-call-centre"
    assert applicant.test_scenario == "a2-applicant"


async def test_existing_tenant_e2e_script_shows_review_after_proceed(life) -> None:
    client, app = life
    raised = await client.post(
        "/api/tenant/opportunities/OPP-103/inquiry",
        json={},
        headers={**tenant(OASIS), "X-Test-Scenario": "a1-existing-tenant"},
    )
    assert raised.status_code == 200, raised.text
    session_id = raised.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    assert session.test_scenario == "a1-existing-tenant"
    events = await chat_action(client, session_id, "proceed_basic_info")
    assert ui_cards(events, "review")


async def test_link_needs_the_basic_info(life) -> None:
    client, app = life
    session_id = await new_assisted(client)
    events = await chat_action(client, session_id, "send_application_link")
    card = ui_cards(events, "send_link")[0]["payload"]
    assert card["can_send"] is False and card["missing"]
    assert outbox(app, template="complete_application") == []


async def test_existing_cr_continue_for_them_loads_the_tenant_record(life) -> None:
    client, app = life
    session_id = await new_assisted(client)
    session = await app.state.session_store.get(session_id)
    session.draft.fields[FieldKey.CR_NUMBER].value = "1010000000"
    session.draft.cr_status = "existing"
    events = await chat_action(client, session_id, "existing_cr_choice", {"choice": "continue"})
    assert ui_cards(events, "existing_cr_choice")[0]["payload"]["chosen"] == "continue"
    draft = session.draft
    assert draft.cr_status == "tenant" and session.tenant_id == OASIS
    company = draft.fields[FieldKey.COMPANY_NAME]
    assert (company.value, company.source, company.confirmed) == (
        "Oasis Coffee Company",
        Source.VERIFIED,
        False,
    )
    assert draft.fields[FieldKey.BRAND_NAME_EN].value == "Oasis Coffee"
    assert draft.documents["company_profile"].on_file is True
    stored = app.state.services.storage.path_for(
        [session_id], draft.documents["company_profile"].file_id
    )
    assert stored is not None and stored.read_bytes().startswith(b"%PDF")


async def test_existing_cr_ask_them_to_sign_in_closes_the_chat(life) -> None:
    client, app = life
    session_id = await new_assisted(client)
    session = await app.state.session_store.get(session_id)
    session.draft.fields[FieldKey.CR_NUMBER].value = "1010000000"
    session.draft.cr_status = "existing"
    await chat_action(client, session_id, "existing_cr_choice", {"choice": "sign_in"})
    assert session.closed == "redirected_to_sign_in"
    reasons = [
        e["payload"].get("reason")
        for e in app.state.services.audit.events(session_id)
        if e["type"] == "inquiry_redirected"
    ]
    assert reasons == ["sign_in"]


async def test_verify_cr_in_assisted_mode_offers_the_choice(tmp_path: Path) -> None:
    steps = [tool_call("verify_cr", {"cr_number": "1010000000"}, "v1"), {"content": "Choose."}]
    async with channel_app(tmp_path, steps) as (client, _app):
        session_id = await new_assisted(client)
        events = await chat_message(client, session_id, "CR 1010000000")
        card = ui_cards(events, "existing_cr_choice")[0]["payload"]
        assert card["company_name"] == "Oasis Coffee Company"
        assert {o["value"] for o in card["options"]} == {"sign_in", "continue"}


async def test_handoff_cases_open_the_same_inquiry(life) -> None:
    client, app = life
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    await chat_action(client, session_id, "request_handoff")
    handoffs = (await client.get("/api/callcentre/handoffs", headers={"X-Staff-Id": STAFF})).json()
    case = next(h for h in handoffs if h["inquiry_id"] == session_id)
    opened = await client.post(
        f"/api/callcentre/handoffs/{case['case_id']}/open", headers={"X-Staff-Id": STAFF}
    )
    assert opened.json()["session_id"] == session_id
    assert "Picked up from the applicant's chat" in opened.json()["messages"][-1]["text"]
    assert (await app.state.session_store.get(session_id)).staff_id == STAFF


# ---- Public page (existing CR) ---------------------------------------------------------


async def test_public_page_sign_in_policy_shows_the_button(tmp_path: Path) -> None:
    steps = [tool_call("verify_cr", {"cr_number": "1010000000"}, "v1"), {"content": "Sign in."}]
    async with channel_app(tmp_path, steps) as (client, app):
        session_id = (await client.post("/api/sessions")).json()["session_id"]
        events = await chat_message(client, session_id, "My CR is 1010000000")
        card = ui_cards(events, "sign_in_prompt")[0]["payload"]
        assert card["sign_in_url"].endswith("/tenant")
        assert any(
            e["type"] == "inquiry_redirected" for e in app.state.services.audit.events(session_id)
        )


async def test_public_page_allow_inquiry_prefills_the_tenant_record(tmp_path: Path) -> None:
    steps = [tool_call("verify_cr", {"cr_number": "1010000000"}, "v1"), {"content": "Check."}]
    async with channel_app(tmp_path, steps) as (client, app):
        # After create_app, which installs the policy file.
        allow = get_policy().with_changes(existing_tenant_policy="allow_inquiry")
        with use_policy(allow):
            session_id = (await client.post("/api/sessions")).json()["session_id"]
            events = await chat_message(client, session_id, "My CR is 1010000000")
            assert ui_cards(events, "basic_info_review")
            session = await app.state.session_store.get(session_id)
            assert session.draft.cr_status == "tenant"
            assert session.draft.fields[FieldKey.COMPANY_NAME].source == Source.VERIFIED
            assert session.draft.email_verified is False  # the public page still verifies


# ---- Tenant Central (existing tenant, signed in) ----------------------------------------


def tenant(tenant_id: str) -> dict[str, str]:
    return {"X-Tenant-Id": tenant_id}


async def test_portal_needs_a_tenant_and_filters_opportunities(life) -> None:
    client, _app = life
    assert (await client.get("/api/tenant/opportunities")).status_code == 401
    tenants = (await client.get("/api/tenant/tenants")).json()
    assert {t["id"] for t in tenants} == {OASIS, AL_NOOR}
    jeddah = (
        await client.get("/api/tenant/opportunities?city=jeddah", headers=tenant(OASIS))
    ).json()
    assert jeddah and all(o["city_id"] == "jeddah" for o in jeddah)
    media = (
        await client.get("/api/tenant/opportunities?unit_type=media", headers=tenant(OASIS))
    ).json()
    assert [o["id"] for o in media] == ["OPP-104"]


async def test_raise_inquiry_prefills_verifies_and_preselects(life) -> None:
    client, app = life
    raised = await client.post(
        "/api/tenant/opportunities/OPP-103/inquiry", json={}, headers=tenant(OASIS)
    )
    assert raised.status_code == 200, raised.text
    body = raised.json()
    assert "Welcome back, Layla" in body["messages"][0]["text"]
    assert body["cards"][0]["card_type"] == "basic_info_review"
    session = await app.state.session_store.get(body["session_id"])
    draft = session.draft
    assert session.channel == "existing_tenant" and session.tenant_id == OASIS
    assert draft.fields[FieldKey.MALLS].value == ["jeddah-mall-b"]
    assert draft.fields[FieldKey.UNIT_TYPE].source == Source.USER
    assert (draft.fields[FieldKey.AREA_MIN].value, draft.fields[FieldKey.AREA_MAX].value) == (
        150,
        220,
    )
    assert draft.email_verified and draft.mobile_verified  # signed in
    assert {"company_profile", "brand_profile"} <= {d.value for d in draft.documents}


async def test_several_brands_asks_which_one(life) -> None:
    client, app = life
    raised = (
        await client.post(
            "/api/tenant/opportunities/OPP-101/inquiry", json={}, headers=tenant(AL_NOOR)
        )
    ).json()
    assert "Which brand is this for" in raised["messages"][0]["text"]
    session = await app.state.session_store.get(raised["session_id"])
    assert session.draft.fields[FieldKey.BRAND_NAME_EN].value is None
    chosen = (
        await client.post(
            "/api/tenant/opportunities/OPP-101/inquiry",
            json={"brand_id": "TB-3"},
            headers=tenant(AL_NOOR),
        )
    ).json()
    picked = await app.state.session_store.get(chosen["session_id"])
    assert picked.draft.fields[FieldKey.BRAND_NAME_EN].value == "Noor Beauty"
    bad = await client.post(
        "/api/tenant/opportunities/OPP-101/inquiry",
        json={"brand_id": "TB-1"},
        headers=tenant(AL_NOOR),
    )
    assert bad.status_code == 400


async def test_existing_tenant_submits_and_gets_contacts_prefilled(life) -> None:
    client, app = life
    raised = (
        await client.post(
            "/api/tenant/opportunities/OPP-101/inquiry", json={}, headers=tenant(OASIS)
        )
    ).json()
    session_id = raised["session_id"]
    await chat_action(client, session_id, "proceed_basic_info")
    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    success = ui_cards(events, "success")
    assert success, events
    reference = success[0]["payload"]["reference"]
    case = app.state.services.cases.get(reference)
    assert (case.channel, case.tenant_id, case.created_by) == ("existing_tenant", OASIS, OASIS)

    mine = (await client.get("/api/tenant/inquiries", headers=tenant(OASIS))).json()
    assert [m["reference"] for m in mine] == [reference]
    assert "/inquiry/status/" in mine[0]["tracking_url"]
    assert (await client.get("/api/tenant/inquiries", headers=tenant(AL_NOOR))).json() == []

    queue = (await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_CENTRAL})).json()
    assert next(q for q in queue if q["reference"] == reference)["channel"] == "existing_tenant"
    assert (await act(client, STORE_CENTRAL, reference, "approve_first")).status_code == 200
    case = app.state.services.cases.get(reference)
    roles = {c.role: c for c in case.tenant_contacts}
    assert set(roles) == {"authorized_signatory", "billing_contact"}
    assert roles["billing_contact"].email.source == Source.VERIFIED
    assert roles["billing_contact"].email.confirmed is False
    # Layla already has a Tenant Central account: no invitation for her.
    assert outbox(app, "layla.hassan@oasiscoffee.example", "azure_ad_invitation") == []


@pytest.mark.parametrize("flag", ["callcentre_console", "tenant_portal"])
async def test_channel_routes_are_off_without_their_flag(tmp_path: Path, flag: str) -> None:
    settings = lifecycle_settings(tmp_path).model_copy(update={flag: False})
    application = create_app(settings=settings)
    path = "/api/callcentre/staff" if flag == "callcentre_console" else "/api/tenant/tenants"
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://t") as c:
        assert (await c.get(path)).status_code == 404


def test_prefill_needs_no_agent() -> None:
    from app.domain.tenant_prefill import prefill_from_tenant
    from app.services.tenants import TenantDirectory

    oasis = TenantDirectory().get_by_id(OASIS)
    draft, written = prefill_from_tenant(new_inquiry_draft(), oasis, load_master_data())
    assert draft.fields[FieldKey.MOBILE].value == "+966551110001"
    assert {"company_name", "brand_name_ar", "sales_category", "email"} <= set(written)
