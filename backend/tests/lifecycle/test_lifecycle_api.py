"""The review lifecycle end to end (L4): routing, the console API, case links, effects."""

from pathlib import Path

from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.domain.master import load_master_data
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from app.workflow.contacts import write_contacts
from app.workflow.effects import run_effects
from app.workflow.models import CaseStatus, WorkflowEvent
from httpx import ASGITransport, AsyncClient
from tests.lifecycle.conftest import (
    APPLICANT,
    MEDIA_EASTERN,
    STORE_CENTRAL,
    STORE_WESTERN,
    act,
    lifecycle_settings,
    outbox,
    submit_case,
    token_from,
)
from tests.scenarios.helpers import chat_action, ui_cards, upload_document

CENTRAL_REVIEWER_EMAIL = "faisal.alqahtani@cenomi.example"


def _case(app, reference):
    return app.state.services.cases.get(reference)


def _runtime(app) -> AgentRuntime:
    return AgentRuntime(
        services=app.state.services, master=load_master_data(), settings=app.state.settings
    )


async def _open(client, link_or_token: str) -> dict:
    token = token_from(link_or_token) if link_or_token.startswith("http") else link_or_token
    response = await client.post("/api/cases/open", json={"token": token})
    assert response.status_code == 200, response.text
    return response.json()


def _cards(opened: dict, card_type: str) -> list[dict]:
    return [c for c in opened["cards"] if c["card_type"] == card_type]


# ---- routing and access (T8, X6) ------------------------------------------------------


async def test_submit_routes_to_the_queue_and_notifies_its_reviewers(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    case = _case(app, reference)
    assert case.status == CaseStatus.FIRST_REVIEW
    assert case.review_queue.model_dump() == {
        "product_line": "store",
        "region": "central",
        "role": "rlm_store",
    }
    assigned = outbox(app, CENTRAL_REVIEWER_EMAIL, "review_assigned")
    assert len(assigned) == 1 and f"/review/cases/{reference}" in assigned[0]["body"]

    mine = await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_CENTRAL})
    assert [c["reference"] for c in mine.json()] == [reference]
    assert mine.json()[0]["waiting_on"] == "reviewer"
    other = await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_WESTERN})
    assert other.json() == []
    hidden = await client.get(
        f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": STORE_WESTERN}
    )
    assert hidden.status_code == 404
    refused = await act(client, STORE_WESTERN, reference, "approve_first")
    assert refused.status_code == 404
    assert _case(app, reference).status == CaseStatus.FIRST_REVIEW


async def test_media_eastern_lands_in_its_own_queue(life) -> None:
    client, app = life
    reference = await submit_case(client, app, unit_type="media", mall="dammam-mall-a")
    queue = _case(app, reference).review_queue
    assert (queue.role, queue.region) == ("rplm_media", "eastern")
    media = await client.get("/api/review/cases", headers={"X-Reviewer-Id": MEDIA_EASTERN})
    assert [c["reference"] for c in media.json()] == [reference]
    store = await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_CENTRAL})
    assert store.json() == []


async def test_review_api_needs_a_known_reviewer(life) -> None:
    client, _app = life
    assert (await client.get("/api/review/me")).status_code == 401
    me = await client.get("/api/review/me", headers={"X-Reviewer-Id": STORE_CENTRAL})
    assert me.json()["role"] == "rlm_store"
    reviewers = (await client.get("/api/review/reviewers")).json()
    assert {r["id"] for r in reviewers} >= {STORE_CENTRAL, MEDIA_EASTERN}
    assert all(r["role"] != "customer_care" for r in reviewers)


async def test_console_is_off_without_the_flag(tmp_path: Path) -> None:
    settings = lifecycle_settings(tmp_path).model_copy(update={"reviewer_console": False})
    app = create_app(settings=settings, model_factory=lambda: ScriptedChatModel(steps=[]))
    app.state.settings = settings
    app.state.session_store = SessionStore(ttl_minutes=120)
    app.state.services = build_services(settings)
    app.state.graph = build_graph(model_factory=lambda: ScriptedChatModel(steps=[]))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/review/me", headers={"X-Reviewer-Id": STORE_CENTRAL})
        assert response.status_code == 404


async def test_action_errors(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    unknown = await act(client, STORE_CENTRAL, reference, "fast_track")
    assert unknown.status_code == 400 and unknown.json()["error"]["code"] == "unknown_action"
    no_remarks = await act(client, STORE_CENTRAL, reference, "reject", remarks=" ")
    assert no_remarks.status_code == 400
    assert no_remarks.json()["error"]["code"] == "invalid_payload"
    too_early = await act(client, STORE_CENTRAL, reference, "approve")
    assert too_early.status_code == 409
    assert too_early.json()["error"]["code"] == "illegal_transition"
    audit = (await client.get(f"/api/dev/audit/{reference}")).json()["events"]
    refused = [
        e for e in audit if e["type"] == "case_transition" and e["payload"]["outcome"] != "applied"
    ]
    assert {e["payload"]["outcome"] for e in refused} == {"invalid_payload", "illegal_transition"}


async def test_case_detail_shows_brief_timeline_and_legal_actions(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    detail = (
        await client.get(f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": STORE_CENTRAL})
    ).json()
    assert sorted(detail["legal_actions"]) == ["approve_first", "reject", "request_reupload"]
    assert detail["brief"]["reference"] == reference
    assert detail["brief"]["stage_label"] == "First review"
    assert detail["brief"]["queue_role"] == "Regional Leasing Manager (Store)"
    assert detail["rejection_categories"]
    types = [e["type"] for e in detail["timeline"]]
    assert "submit_result" in types and "case_transition" in types
    routed = next(e for e in detail["timeline"] if e["summary"].startswith("Routed"))
    assert routed["actor"] == "system"


# ---- re-upload loop (T2, X1, X3) ------------------------------------------------------


async def test_reupload_loop_from_the_email_link(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    response = await act(
        client,
        STORE_CENTRAL,
        reference,
        "request_reupload",
        doc_types=["brand_profile"],
        remarks="The brand profile is from 2019; please send the current one.",
    )
    assert response.status_code == 200
    assert response.json()["brief"]["waiting_on"] == "applicant"
    mail = outbox(app, APPLICANT, "reupload_request")
    assert len(mail) == 1
    assert "Brand Profile" in mail[0]["body"] and "from 2019" in mail[0]["body"]

    opened = await _open(client, mail[0]["links"][0])
    session_id = opened["session_id"]
    status = _cards(opened, "case_status")[0]["payload"]
    assert status["stage"] == "first_review"
    assert status["open_requests"][0]["remarks"].startswith("The brand profile is from 2019")
    reupload = _cards(opened, "document_upload")[0]["payload"]
    assert reupload["mode"] == "reupload"
    assert reupload["requested_doc_types"] == ["brand_profile"]
    assert [d["doc_type"] for d in reupload["docs"]] == ["brand_profile"]
    session = await app.state.session_store.get(session_id)
    assert (session.mode, session.case_id) == ("case", reference)

    blocked = await chat_action(client, session_id, "resubmit_documents")
    assert ui_cards(blocked, "document_upload")
    assert _case(app, reference).status == CaseStatus.REUPLOAD_REQUESTED

    uploaded = await upload_document(
        client, session_id, "brand_profile", "brand_2026.pdf", b"%PDF-new"
    )
    assert uploaded["status_code"] == 200
    assert uploaded["body"]["card"]["payload"]["mode"] == "reupload"
    assert uploaded["body"]["card"]["payload"]["required_uploaded"] == 1

    done = await chat_action(client, session_id, "resubmit_documents")
    assert ui_cards(done, "case_status")[0]["payload"]["stage"] == "first_review"
    case = _case(app, reference)
    assert case.status == CaseStatus.FIRST_REVIEW
    assert case.draft.documents["brand_profile"].file_name == "brand_2026.pdf"
    assert [d.file_id for d in case.document_history] == ["br-1"]
    assert len(outbox(app, CENTRAL_REVIEWER_EMAIL, "reupload_received")) == 1

    file_id = case.draft.documents["brand_profile"].file_id
    download = await client.get(
        f"/api/review/cases/{reference}/documents/{file_id}",
        headers={"X-Reviewer-Id": STORE_CENTRAL},
    )
    assert download.status_code == 200 and download.content == b"%PDF-new"

    # Opening the link again reuses the same chat.
    again = await _open(client, mail[0]["links"][0])
    assert again["session_id"] == session_id


# ---- first approval, contacts, final approval, Yardi (T1, X5) ---------------------------


async def _approve_first(client, app, reference) -> None:
    response = await act(client, STORE_CENTRAL, reference, "approve_first")
    assert response.status_code == 200, response.text


async def test_first_approval_invites_and_requests_contacts(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _approve_first(client, app, reference)
    case = _case(app, reference)
    assert case.status == CaseStatus.SECOND_REVIEW
    assert case.open_request("contacts") is not None  # automatic (requirements §7.1.1 b)
    for template in ("azure_ad_invitation", "first_level_approved", "contacts_request"):
        assert len(outbox(app, APPLICANT, template)) == 1, template
    invitation = case.onboarding.invitations[0]
    assert invitation.role == "primary_contact"
    accept_link = outbox(app, APPLICANT, "azure_ad_invitation")[0]["links"][0]
    accepted = await client.get(accept_link.replace("http://localhost:8000", ""))
    assert accepted.status_code == 200
    assert _case(app, reference).onboarding.invitations[0].accepted_at is not None
    assert app.state.services.identity.has_account(APPLICANT)

    # The same applicant again: no second invitation once they have an account.
    second = await submit_case(client, app)
    await _approve_first(client, app, second)
    assert len(outbox(app, APPLICANT, "azure_ad_invitation")) == 1


async def _contacts_link(app) -> str:
    return outbox(app, APPLICANT, "contacts_request")[0]["links"][0]


async def test_contacts_then_final_approval_sends_the_lead(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _approve_first(client, app, reference)
    opened = await _open(client, await _contacts_link(app))
    session_id = opened["session_id"]
    assert _cards(opened, "contacts")[0]["payload"]["can_submit"] is False

    session = await app.state.session_store.get(session_id)
    contacts, errors = write_contacts(
        [],
        [
            {"role": "authorized_signatory", "same_as_primary": True},
            {
                "role": "billing_contact",
                "first_name": "Omar",
                "last_name": "Saleh",
                "email": "omar@beanstreet.example",
                "contact_number": "٠٥٥١٢٣٤٥٦٧",
            },
        ],
        session.draft,
    )
    assert errors == {}
    session.contacts_draft = [c.model_dump(mode="json") for c in contacts]
    sent = await chat_action(client, session_id, "submit_contacts")
    assert ui_cards(sent, "case_status")[0]["payload"]["open_requests"] == []
    case = _case(app, reference)
    assert {c.role for c in case.tenant_contacts} == {"authorized_signatory", "billing_contact"}
    assert case.tenant_contacts[1].mobile.value == "+966551234567"
    assert len(outbox(app, CENTRAL_REVIEWER_EMAIL, "contacts_received")) == 1

    approved = await act(client, STORE_CENTRAL, reference, "approve")
    assert approved.status_code == 200, approved.text
    case = _case(app, reference)
    assert case.status == CaseStatus.SENT_TO_YARDI
    assert case.yardi.lead_ref and case.yardi.lead_ref.startswith("YL-")
    assert f"lead:{reference}" in app.state.services.yardi.leads
    assert len(outbox(app, "omar@beanstreet.example", "azure_ad_invitation")) == 1
    assert len(outbox(app, APPLICANT, "inquiry_accepted")) == 1

    status_card = _cards(await _open(client, await _contacts_link(app)), "case_status")[0]
    assert status_card["payload"]["status"] == "sent_to_yardi"
    assert status_card["payload"]["outcome"] == "approved"


async def test_yardi_failures_are_retried_until_acknowledged(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _approve_first(client, app, reference)
    case = _case(app, reference)
    case.requests[0].status = "withdrawn"
    case.tenant_contacts = [
        *write_contacts(
            [],
            [
                {"role": "authorized_signatory", "same_as_primary": True},
                {"role": "billing_contact", "same_as_primary": True},
            ],
            case.draft,
        )[0]
    ]
    app.state.services.cases.save(case)
    app.state.services.gateway.set_session_faults(reference, "yardi:unavailable:2")
    response = await act(client, STORE_CENTRAL, reference, "approve")
    assert response.status_code == 200
    case = _case(app, reference)
    assert case.status == CaseStatus.SENT_TO_YARDI
    assert case.yardi.attempts == 2
    assert [e.name for e in case.events][-3:] == ["yardi_failed", "yardi_failed", "sent_to_yardi"]


async def test_yardi_down_flags_the_case_for_operations(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _approve_first(client, app, reference)
    case = _case(app, reference)
    case.requests[0].status = "withdrawn"
    case.tenant_contacts = write_contacts(
        [],
        [
            {"role": "authorized_signatory", "same_as_primary": True},
            {"role": "billing_contact", "same_as_primary": True},
        ],
        case.draft,
    )[0]
    app.state.services.cases.save(case)
    app.state.services.gateway.set_session_faults(reference, "yardi:unavailable")
    await act(client, STORE_CENTRAL, reference, "approve")
    case = _case(app, reference)
    assert case.status == CaseStatus.APPROVED
    assert case.yardi.needs_operations is True
    queue = (await client.get("/api/review/cases", headers={"X-Reviewer-Id": STORE_CENTRAL})).json()
    assert next(c for c in queue if c["reference"] == reference)["needs_operations"] is True


# ---- rejection (T3) and sales data (T4) ------------------------------------------------


async def test_rejection_email_and_the_case_page(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    response = await act(
        client,
        STORE_CENTRAL,
        reference,
        "reject",
        remarks="The concept doesn't fit this mall's tenant mix.",
        reason_category="not_a_fit",
    )
    assert response.status_code == 200
    mail = outbox(app, APPLICANT, "inquiry_rejected")
    assert len(mail) == 1 and "tenant mix" in mail[0]["body"]
    assert "raise a new inquiry" in mail[0]["body"]
    tracking = outbox(app, APPLICANT, "submission_email")[0]["links"][0]
    opened = await _open(client, tracking)
    status = _cards(opened, "case_status")[0]["payload"]
    assert status["outcome"] == "rejected"
    assert "tenant mix" in status["outcome_remarks"]
    assert _cards(opened, "document_upload") == []


async def test_sales_data_loop(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await _approve_first(client, app, reference)
    response = await act(
        client, STORE_CENTRAL, reference, "request_sales_data", remarks="Monthly, first year."
    )
    assert response.status_code == 200
    link = outbox(app, APPLICANT, "sales_data_request")[0]["links"][0]
    opened = await _open(client, link)
    session_id = opened["session_id"]
    assert _cards(opened, "sales_data_upload")[0]["payload"]["uploaded"] is False

    early = await chat_action(client, session_id, "submit_sales_data")
    assert not ui_cards(early, "case_status")
    uploaded = await upload_document(client, session_id, "sales_data", "sales.xlsx", b"PK-sales")
    assert uploaded["status_code"] == 200
    assert uploaded["body"]["card"]["card_type"] == "sales_data_upload"
    await chat_action(client, session_id, "submit_sales_data")
    case = _case(app, reference)
    assert case.sales_data is not None and case.sales_data.file_name == "sales.xlsx"
    assert len(outbox(app, CENTRAL_REVIEWER_EMAIL, "sales_data_received")) == 1


async def test_sales_data_is_not_an_intake_document(life) -> None:
    client, _app = life
    session_id = (await client.post("/api/sessions")).json()["session_id"]
    refused = await upload_document(client, session_id, "sales_data", "sales.xlsx", b"PK")
    assert refused["status_code"] == 400


async def test_links_need_a_valid_token(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    bad = await client.post("/api/cases/open", json={"token": reference})
    assert bad.status_code == 400


async def test_tracking_page_follows_the_case(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    await act(client, STORE_CENTRAL, reference, "approve_first")
    tracking = outbox(app, APPLICANT, "submission_email")[0]["links"][0]
    status = await client.get(f"/api/inquiries/{reference}", params={"t": token_from(tracking)})
    body = status.json()
    assert body["current_stage"] == "second_review"
    assert [s["label"] for s in body["stages"]][2] == "Lead — second review"
    assert body["waiting_on_you"] == ["Add company contacts"]


# ---- effects (X5) -----------------------------------------------------------------------


async def test_effects_run_once_and_a_failure_never_rolls_back(life) -> None:
    client, app = life
    reference = await submit_case(client, app)
    app.state.services.gateway.set_session_faults(reference, "notifications:unavailable:1")
    await act(client, STORE_CENTRAL, reference, "reject", remarks="Not a fit.")
    case = _case(app, reference)
    assert case.status == CaseStatus.REJECTED
    assert outbox(app, APPLICANT, "inquiry_rejected") == []
    audit = (await client.get(f"/api/dev/audit/{reference}")).json()["events"]
    failed = [
        e for e in audit if e["type"] == "effect_run" and e["payload"]["outcome"] == "unavailable"
    ]
    assert failed

    # A retry sends it once; another retry sends nothing more.
    event = WorkflowEvent(name="rejected", payload={})
    await run_effects(_runtime(app), case, event)
    await run_effects(_runtime(app), _case(app, reference), event)
    assert len(outbox(app, APPLICANT, "inquiry_rejected")) == 1
