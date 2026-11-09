"""R4 (demo feedback §3.8, D13): a signed-in tenant raising from Leasing Opportunities.

Every inquiry is a new brand under the same company: company name and address come from
Yardi by CR, verified and unconfirmed; no brand is prefilled; both profiles are uploaded
afresh, and the Company Profile is checked against the Yardi record (R3 checks).
"""

from __future__ import annotations

from typing import Any

from app.domain.document_checks import document_mismatches
from app.domain.draft_ops import write_fields
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey, Source
from app.domain.rules import can_submit
from app.services.yardi import YardiCompany
from tests.lifecycle.conftest import STORE_CENTRAL
from tests.scenarios.helpers import (
    chat_action,
    chat_message,
    token_text,
    ui_cards,
    upload_document,
)

OASIS = "T-1001"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def _raise(client: Any, tenant_id: str = OASIS) -> dict[str, Any]:
    raised = await client.post(
        "/api/tenant/opportunities/OPP-101/inquiry", json={}, headers={"X-Tenant-Id": tenant_id}
    )
    assert raised.status_code == 200, raised.text
    return raised.json()


def _audit(app: Any, session_id: str, event: str) -> list[dict[str, Any]]:
    return [e["payload"] for e in app.state.services.audit.events(session_id) if e["type"] == event]


async def test_company_comes_from_yardi_verified_and_unconfirmed(life) -> None:
    client, app = life
    body = await _raise(client)
    session = await app.state.session_store.get(body["session_id"])
    draft = session.draft
    for key, value in (
        (FieldKey.COMPANY_NAME, "Oasis Coffee Company"),
        (FieldKey.COMPANY_ADDRESS, "Prince Sultan Road, Al Rawdah, Jeddah"),
    ):
        field = draft.fields[key]
        assert (field.value, field.source, field.confirmed) == (value, Source.VERIFIED, False)
    [prefill] = _audit(app, session.id, "tenant_prefill")
    assert (prefill["company_source"], prefill["yardi_company_id"]) == ("yardi", "YC-1301")
    card = body["cards"][0]
    assert card["card_type"] == "basic_info_review"
    assert "Oasis Coffee Company" in str(card["payload"])
    assert "Cenomi record" in body["messages"][0]["text"]


async def test_the_yardi_record_wins_over_the_tenant_record(life, monkeypatch) -> None:
    client, app = life
    yardi = app.state.services.yardi
    renamed = YardiCompany(
        id="YC-1301",
        name="Oasis Coffee Co.",
        active=True,
        brands=[],
        cr_number="1010000000",
        address="Tahlia Street, Jeddah",
    )
    monkeypatch.setattr(yardi, "company_by_cr", lambda cr: renamed if cr == "1010000000" else None)
    session = await app.state.session_store.get((await _raise(client))["session_id"])
    assert session.draft.fields[FieldKey.COMPANY_NAME].value == "Oasis Coffee Co."
    assert session.draft.fields[FieldKey.COMPANY_ADDRESS].value == "Tahlia Street, Jeddah"


async def test_no_yardi_match_falls_back_to_the_tenant_record(life, monkeypatch) -> None:
    client, app = life
    monkeypatch.setattr(app.state.services.yardi, "company_by_cr", lambda _cr: None)
    session = await app.state.session_store.get((await _raise(client))["session_id"])
    assert session.draft.fields[FieldKey.COMPANY_NAME].value == "Oasis Coffee Company"
    [prefill] = _audit(app, session.id, "tenant_prefill")
    assert (prefill["company_source"], prefill["yardi_company_id"]) == ("tenant_record", None)


async def test_no_brand_and_both_profiles_required(life) -> None:
    client, app = life
    session = await app.state.session_store.get((await _raise(client))["session_id"])
    draft = session.draft
    for key in (FieldKey.BRAND_NAME_EN, FieldKey.BRAND_NAME_AR, FieldKey.SALES_CATEGORY):
        assert draft.fields[key].value is None
    assert DocType.COMPANY_PROFILE not in draft.documents
    assert DocType.BRAND_PROFILE not in draft.documents
    assert draft.documents[DocType.CR_CERTIFICATE].on_file  # other documents on file stay
    tokens = {b.token for b in can_submit(draft)}
    assert {"missing_document:company_profile", "missing_document:brand_profile"} <= tokens


async def test_brand_profile_fills_the_new_brand(life) -> None:
    client, app = life
    session_id = (await _raise(client))["session_id"]
    uploaded = await upload_document(
        client, session_id, "brand_profile", "new_brand_profile.pdf", PDF
    )
    assert uploaded["status_code"] == 200, uploaded
    assert set(uploaded["body"]["fields_filled"]) == {"brand_name_en", "sales_category"}
    draft = (await app.state.session_store.get(session_id)).draft
    brand = draft.fields[FieldKey.BRAND_NAME_EN]
    assert (brand.value, brand.source, brand.confirmed) == (
        "Oasis Bakehouse",
        Source.DERIVED,
        False,
    )


async def test_company_profile_is_checked_against_yardi_and_never_blocks(life) -> None:
    client, app = life
    session_id = (await _raise(client))["session_id"]
    await chat_action(client, session_id, "proceed_basic_info")
    uploaded = await upload_document(
        client, session_id, "company_profile", "oasis_company_profile_mismatch.pdf", PDF
    )
    assert uploaded["body"]["mismatches"] == ["company_name"]
    assert uploaded["body"]["fields_filled"] == []  # the Yardi value is kept
    store = app.state.session_store
    session = await store.get(session_id)
    [check] = document_mismatches(session.draft, load_master_data())
    assert (check.field, check.typed, check.document_value) == (
        "company_name",
        "Oasis Coffee Company",
        "Oasis Coffee Trading Establishment",
    )

    # The tenant gives the brand and the Brand Profile; the mismatch doesn't block submit.
    await upload_document(client, session_id, "brand_profile", "brand_profile.pdf", PDF)
    session = await store.get(session_id)
    session.draft, _w, errors = write_fields(
        session.draft,
        [
            (FieldKey.BRAND_NAME_EN.value, "Oasis Bakehouse", Source.USER),
            (FieldKey.BRAND_NAME_AR.value, "مخبز الواحة", Source.USER),
            (FieldKey.SALES_CATEGORY.value, "fnb_cafe", Source.USER),
        ],
        master=load_master_data(),
    )
    assert not errors
    await store.save(session)
    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    [success] = ui_cards(events, "success")
    reference = success["payload"]["reference"]
    detail = (
        await client.get(f"/api/review/cases/{reference}", headers={"X-Reviewer-Id": STORE_CENTRAL})
    ).json()
    assert [c["field"] for c in detail["brief"]["document_checks"]] == ["company_name"]


async def test_a_matching_company_profile_raises_no_flag(life) -> None:
    client, app = life
    session_id = (await _raise(client))["session_id"]
    uploaded = await upload_document(
        client, session_id, "company_profile", "oasis_company_profile.pdf", PDF
    )
    assert uploaded["body"]["mismatches"] == []


async def _raise_scripted(client: Any, scenario: str) -> str:
    raised = await client.post(
        "/api/tenant/opportunities/OPP-101/inquiry",
        json={},
        headers={"X-Tenant-Id": OASIS, "X-Test-Scenario": scenario},
    )
    assert raised.status_code == 200, raised.text
    return str(raised.json()["session_id"])


async def test_rd_signed_in_new_brand_script_plays_turn_by_turn(life) -> None:
    """The Playwright story's script, turn by turn: one reply per turn and no guard retry,
    so every later turn plays its own step."""
    client, app = life
    session_id = await _raise_scripted(client, "rd-signed-in-new-brand")
    log: list[str] = []

    def said(label: str, events: list[tuple[str, dict[str, Any]]]) -> str:
        text = token_text(events)
        cards = [c.get("card_type") for c in ui_cards(events)]
        removed = sum(1 for name, _ in events if name == "message_remove")
        log.append(f"{label}: {text!r} cards={cards} removed={removed}")
        print(log[-1])  # shown under "Captured stdout" when a turn is out of step
        return text

    events = await chat_action(client, session_id, "proceed_basic_info")
    assert "What's the new brand?" in said("proceed", events), log

    events = await chat_message(client, session_id, "I'll upload the Brand Profile")
    assert "both the Company Profile and the Brand Profile" in said("upload choice", events), log
    assert ui_cards(events, "document_upload")

    uploaded = await upload_document(
        client, session_id, "brand_profile", "new_brand_profile.pdf", PDF
    )
    assert set(uploaded["body"]["fields_filled"]) == {"brand_name_en", "sales_category"}
    events = await chat_action(
        client, session_id, "documents_updated", {"doc_type": "brand_profile"}
    )
    assert "filled the brand name and category" in said("brand profile", events), log
    [confirm] = ui_cards(events, "confirm_fields")

    events = await chat_action(client, session_id, "confirm_card", {"card_id": confirm["card_id"]})
    assert "brand name in Arabic" in said("confirm", events), log

    events = await chat_message(client, session_id, "مخبز الواحة")
    assert "upload the Company Profile" in said("arabic", events), log

    uploaded = await upload_document(
        client, session_id, "company_profile", "oasis_company_profile_mismatch.pdf", PDF
    )
    assert uploaded["body"]["mismatches"] == ["company_name"]
    events = await chat_action(
        client, session_id, "documents_updated", {"doc_type": "company_profile"}
    )
    assert "different company name from your Cenomi record" in said("company profile", events), log
    assert ui_cards(events, "review")

    events = await chat_message(client, session_id, "Keep the record's name")
    assert "keep your record's name" in said("keep", events), log

    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    assert ui_cards(events, "success")
    session = await app.state.session_store.get(session_id)
    draft = session.draft
    assert draft.fields[FieldKey.COMPANY_NAME].value == "Oasis Coffee Company"
    assert draft.fields[FieldKey.BRAND_NAME_EN].value == "Oasis Bakehouse"


async def test_a1_existing_tenant_script_types_the_new_brand(life) -> None:
    """The a1 stories' script: the brand typed in one message, both profiles uploaded."""
    client, app = life
    session_id = await _raise_scripted(client, "a1-existing-tenant")

    events = await chat_action(client, session_id, "proceed_basic_info")
    assert "What's the new brand?" in token_text(events)

    events = await chat_message(client, session_id, "Oasis Bakehouse (مخبز الواحة), a café")
    assert "both the Company Profile and the Brand Profile" in token_text(events)
    assert ui_cards(events, "document_upload")

    for doc_type in ("company_profile", "brand_profile"):
        uploaded = await upload_document(client, session_id, doc_type, f"{doc_type}.pdf", PDF)
        assert uploaded["status_code"] == 200
    events = await chat_action(client, session_id, "documents_updated", {})
    assert "Both profiles are in" in token_text(events)
    assert ui_cards(events, "review")

    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    assert ui_cards(events, "success")
