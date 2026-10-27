"""Shared helpers for end-to-end scenario tests."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.models import DocType, FieldKey, InquiryDraft
from app.main import create_app
from app.services.container import build_services
from app.sessions import Session, SessionStore
from httpx import ASGITransport, AsyncClient
from tests.domain.conftest import fill_minimal_collectible


async def read_sse(response) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    current_event: str | None = None
    async for line in response.aiter_lines():
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current_event:
            events.append((current_event, json.loads(line.split(":", 1)[1].strip())))
    return events


async def chat(
    client: AsyncClient,
    session_id: str,
    body: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    async with client.stream(
        "POST",
        f"/api/sessions/{session_id}/chat",
        json=body,
    ) as response:
        assert response.status_code == 200
        return await read_sse(response)


async def chat_message(
    client: AsyncClient,
    session_id: str,
    text: str,
) -> list[tuple[str, dict[str, Any]]]:
    return await chat(client, session_id, {"type": "message", "text": text})


async def chat_action(
    client: AsyncClient,
    session_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    return await chat(
        client,
        session_id,
        {"type": "action", "action": action, "payload": payload or {}},
    )


def token_text(events: list[tuple[str, dict[str, Any]]]) -> str:
    return "".join(data.get("text", "") for name, data in events if name == "token")


def ui_cards(
    events: list[tuple[str, dict[str, Any]]],
    card_type: str | None = None,
) -> list[dict[str, Any]]:
    cards = [data for name, data in events if name == "ui_card"]
    if card_type is None:
        return cards
    return [card for card in cards if card.get("card_type") == card_type]


def last_draft(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any] | None:
    drafts = [data for name, data in events if name == "draft"]
    return drafts[-1] if drafts else None


def confirm_card_id(events: list[tuple[str, dict[str, Any]]]) -> str:
    cards = ui_cards(events, "confirm_fields")
    assert cards, "expected a confirm_fields card"
    return str(cards[-1]["card_id"])


@asynccontextmanager
async def scenario_client(
    settings: Settings,
    steps: list[dict[str, Any]],
) -> AsyncIterator[tuple[AsyncClient, Any]]:
    def factory() -> ScriptedChatModel:
        return ScriptedChatModel(steps=steps)

    application = create_app(settings=settings, model_factory=factory)
    application.state.settings = settings
    application.state.session_store = SessionStore(ttl_minutes=settings.session_ttl_minutes)
    application.state.services = build_services(settings)
    application.state.graph = build_graph(model_factory=factory)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, application


async def new_session(client: AsyncClient) -> str:
    response = await client.post("/api/sessions")
    assert response.status_code == 200
    return response.json()["session_id"]


async def upload_document(
    client: AsyncClient,
    session_id: str,
    doc_type: str,
    file_name: str,
    content: bytes,
) -> dict[str, Any]:
    response = await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": doc_type},
        files={"file": (file_name, content, "application/pdf")},
    )
    return {"status_code": response.status_code, "body": response.json()}


def draft_field(draft: InquiryDraft, key: FieldKey) -> Any:
    return draft.fields[key].value


def draft_meta(draft: InquiryDraft, key: FieldKey) -> tuple[Any, str | None, bool]:
    field = draft.fields[key]
    source = field.source.value if field.source else None
    return field.value, source, field.confirmed


async def attach_required_documents(session: Session, max_bytes: int) -> None:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    draft = session.draft
    for doc_type, file_id, name in (
        (DocType.COMPANY_PROFILE, "co-1", "company.pdf"),
        (DocType.BRAND_PROFILE, "br-1", "brand.pdf"),
    ):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=name,
            size_bytes=100,
            max_bytes=max_bytes,
            uploaded_at=ts,
        )
    session.draft = draft


def ready_to_submit_draft(app, *, cr_skipped: bool = True) -> InquiryDraft:
    from app.domain.master import load_master_data

    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.cr_status = "skipped" if cr_skipped else "new"
    draft.email_verified = True
    draft.mobile_verified = True
    max_bytes = app.state.settings.max_upload_mb * 1024 * 1024
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    for doc_type, file_id, name in (
        (DocType.COMPANY_PROFILE, "co-1", "company.pdf"),
        (DocType.BRAND_PROFILE, "br-1", "brand.pdf"),
    ):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=name,
            size_bytes=100,
            max_bytes=max_bytes,
            uploaded_at=ts,
        )
    return draft


_REFERENCE_RE = re.compile(r"^GEO-(STR|MED|SPC)-\d{6}$")


async def verify_contact(client: AsyncClient, app, session_id: str) -> list[tuple[str, dict]]:
    """Follow the (mock) email link, then enter the mobile code. Returns the OTP turn's events."""
    token = app.state.services.email_verification.demo_token(session_id)
    assert token, "send_verification should have emailed a link"
    await chat_action(client, session_id, "verify_email", {"token": token})
    return await chat_action(client, session_id, "submit_otp", {"code": "1234"})
