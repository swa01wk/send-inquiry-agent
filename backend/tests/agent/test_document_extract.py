"""Type or upload: profiles fill the draft (demo feedback §3.7, D11, D12; ADR-R4).

Through the real upload API with the mock document review service, which answers from the
file name (`mock_world/document_review.json`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agent.actions import handle_ui_action
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.config import Settings
from app.domain import draft_ops
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey, Source
from app.domain.rules import can_submit
from app.main import create_app
from app.services.container import build_services
from app.sessions import SessionStore
from httpx import ASGITransport, AsyncClient
from tests.scenarios.helpers import upload_document

PDF = b"%PDF-1.4\n%sample\n"
MASTER = load_master_data()


@pytest.fixture
async def docs_client(tmp_path: Path):
    settings = Settings(upload_dir=str(tmp_path / "uploads"), max_upload_mb=5)
    application = create_app(
        settings=settings, model_factory=lambda: ScriptedChatModel(steps=[{"content": "OK"}])
    )
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=120)
    application.state.services = build_services(settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, application


async def _session(client: AsyncClient) -> str:
    return str((await client.post("/api/sessions")).json()["session_id"])


def _runtime(app) -> AgentRuntime:  # type: ignore[no-untyped-def]
    return AgentRuntime(services=app.state.services, master=MASTER, settings=app.state.settings)


async def _type(app, session_id: str, **values: str) -> None:  # type: ignore[no-untyped-def]
    store = app.state.session_store
    session = await store.get(session_id)
    session.draft, _w, errors = draft_ops.write_fields(
        session.draft,
        [(key, value, Source.USER) for key, value in values.items()],
        master=MASTER,
    )
    assert not errors, errors
    await store.save(session)


async def test_upload_fills_empty_fields_as_derived_with_evidence(docs_client) -> None:
    client, app = docs_client
    session_id = await _session(client)
    company = await upload_document(
        client, session_id, "company_profile", "company_profile_match.pdf", PDF
    )
    brand = await upload_document(
        client, session_id, "brand_profile", "brand_profile_match.pdf", PDF
    )
    assert company["status_code"] == 200, company["body"]
    assert company["body"]["fields_filled"] == ["company_name", "company_address"]
    assert company["body"]["mismatches"] == []
    assert set(company["body"]["draft"]["changed_keys"]) == {"company_name", "company_address"}
    assert brand["body"]["fields_filled"] == ["brand_name_en", "sales_category"]

    session = await app.state.session_store.get(session_id)
    name = session.draft.fields[FieldKey.COMPANY_NAME]
    assert name.value == "Bean Street Trading Co."
    assert name.source == Source.DERIVED and name.confirmed is False
    assert name.evidence is not None
    assert name.evidence.startswith("Company Profile: company_profile_match.pdf, uploaded ")
    assert session.draft.fields[FieldKey.SALES_CATEGORY].value == "fnb_cafe"
    assert session.draft.documents[DocType.COMPANY_PROFILE].filled_fields == [
        "company_name",
        "company_address",
    ]

    # Golden rule 2 / I4: nothing filled from a document is submitted unconfirmed.
    blockers = {b.token for b in can_submit(session.draft)}
    assert "unconfirmed_field:company_name" in blockers
    assert "unconfirmed_field:sales_category" in blockers


async def test_a_typed_value_is_never_overwritten_and_a_difference_is_flagged(
    docs_client,
) -> None:
    client, app = docs_client
    session_id = await _session(client)
    await _type(app, session_id, company_name="Bean Street Trading Co.")
    uploaded = await upload_document(
        client, session_id, "company_profile", "company_profile_mismatch.pdf", PDF
    )
    body = uploaded["body"]
    assert body["fields_filled"] == ["company_address"]  # the empty one only
    assert body["mismatches"] == ["company_name"]

    session = await app.state.session_store.get(session_id)
    name = session.draft.fields[FieldKey.COMPANY_NAME]
    assert (name.value, name.source, name.confirmed) == (
        "Bean Street Trading Co.",
        Source.USER,
        True,
    )
    # A mismatch never blocks submit.
    assert not any("mismatch" in b.token for b in can_submit(session.draft))

    audit = app.state.services.audit.events(session_id)
    flagged = [e for e in audit if e["type"] == "document_mismatch"]
    assert flagged[-1]["payload"] == {"doc_type": "company_profile", "fields": ["company_name"]}
    assert "Bean Street Holding Company" not in json.dumps(audit)


async def test_documents_updated_tells_the_agent_field_names_only(docs_client) -> None:
    client, app = docs_client
    session_id = await _session(client)
    await _type(app, session_id, company_name="Bean Street Trading Co.")
    await upload_document(
        client, session_id, "company_profile", "company_profile_mismatch.pdf", PDF
    )
    session = await app.state.session_store.get(session_id)
    result = await handle_ui_action(
        "documents_updated", {"doc_type": "company_profile"}, session, _runtime(app)
    )
    note = str(result.note.content)
    assert "[ui_event] document_fields company_profile filled=company_address" in note
    assert "[ui_event] document_mismatch company_name" in note
    assert "[ui_event] documents_pending brand_profile" in note
    assert "Bean Street Holding Company" not in note
    assert "King Fahd" not in note

    # Without a doc type (all documents in, the older call): only the status line.
    plain = await handle_ui_action("documents_updated", {}, session, _runtime(app))
    assert str(plain.note.content) == "[ui_event] documents_pending brand_profile"


async def test_a_replaced_profile_takes_back_its_values_and_they_need_confirming_again(
    docs_client,
) -> None:
    client, app = docs_client
    session_id = await _session(client)
    await upload_document(client, session_id, "company_profile", "company_profile_match.pdf", PDF)
    store = app.state.session_store
    session = await store.get(session_id)
    session.draft = draft_ops.confirm(session.draft, ["company_name", "company_address"])
    await store.save(session)
    assert session.draft.fields[FieldKey.COMPANY_NAME].confirmed is True

    replaced = await upload_document(
        client, session_id, "company_profile", "company_profile_mismatch.pdf", PDF
    )
    assert replaced["body"]["fields_filled"] == ["company_name", "company_address"]
    assert replaced["body"]["mismatches"] == []  # the new file's own values
    session = await store.get(session_id)
    name = session.draft.fields[FieldKey.COMPANY_NAME]
    assert name.value == "Bean Street Holding Company"
    assert name.confirmed is False
    assert name.evidence is not None and "company_profile_mismatch.pdf" in name.evidence
    assert "unconfirmed_field:company_name" in {b.token for b in can_submit(session.draft)}


async def test_an_edited_value_survives_a_replaced_profile(docs_client) -> None:
    client, app = docs_client
    session_id = await _session(client)
    await upload_document(client, session_id, "company_profile", "company_profile_match.pdf", PDF)
    await _type(app, session_id, company_name="Bean Street Trading Company")
    replaced = await upload_document(
        client, session_id, "company_profile", "company_profile_mismatch.pdf", PDF
    )
    assert "company_name" not in replaced["body"]["fields_filled"]
    assert replaced["body"]["mismatches"] == ["company_name"]
    session = await app.state.session_store.get(session_id)
    assert session.draft.fields[FieldKey.COMPANY_NAME].value == "Bean Street Trading Company"


async def test_removing_a_profile_removes_what_it_filled(docs_client) -> None:
    client, app = docs_client
    session_id = await _session(client)
    await upload_document(client, session_id, "company_profile", "company_profile_match.pdf", PDF)
    removed = await client.delete(f"/api/sessions/{session_id}/documents/company_profile")
    assert removed.status_code == 200, removed.json()
    session = await app.state.session_store.get(session_id)
    assert session.draft.fields[FieldKey.COMPANY_NAME].value is None
    assert session.draft.fields[FieldKey.COMPANY_ADDRESS].value is None


async def test_files_the_mock_doesnt_know_fill_nothing(docs_client) -> None:
    # Every existing story uploads company_profile.pdf / brand_profile.pdf: unchanged.
    client, app = docs_client
    session_id = await _session(client)
    uploaded = await upload_document(
        client, session_id, "company_profile", "company_profile.pdf", PDF
    )
    assert uploaded["body"]["fields_filled"] == []
    assert uploaded["body"]["mismatches"] == []
    session = await app.state.session_store.get(session_id)
    assert session.draft.fields[FieldKey.COMPANY_NAME].value is None
