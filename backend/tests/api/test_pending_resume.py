"""Flow v2 "Continue my inquiry" (spec flow-v2-alignment §3.3, FV12–FV13; day F3).

A verified, unsubmitted v2 inquiry is pending. "Continue my inquiry" with the email sends a
`resume_link` email whose link re-verifies the address and resumes that chat. The reply is
the same whether or not one exists, and the email never reaches the model.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from app.agent.model import ScriptedChatModel
from app.agent.pending import RESUME_PENDING_REPLY
from app.domain.models import FieldKey
from app.store.models import InquiryStatus
from app.store.session_bridge import inquiry_id_for
from httpx import AsyncClient
from tests.scenarios.helpers import chat_action, token_text

pytestmark = pytest.mark.intake_v2


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "MODEL TURN"}] * 4)


def _email() -> str:
    return f"sara.{uuid.uuid4().hex[:8]}@brand.example"


async def _pending_session(client: AsyncClient, app, email: str) -> str:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    store = app.state.session_store
    session = await store.get(session_id)
    draft = session.draft.model_copy(deep=True)
    draft.cr_status = "skipped"
    draft.fields[FieldKey.EMAIL].value = email
    draft.email_verified = True
    draft.verified_at = datetime.now(tz=UTC)
    session.draft = draft
    await store.save(session)
    inquiry = await store.inquiry_repo.get(inquiry_id_for(session))
    assert inquiry.status == InquiryStatus.PENDING
    return session_id


async def _new_session_id(client: AsyncClient) -> str:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    return created.json()["session_id"]


def _resume_mail(app, email: str) -> list[dict]:
    return [
        m
        for m in app.state.services.notifications.messages(to=email)
        if m["template"] == "resume_link"
    ]


async def test_resume_emails_a_link_that_resumes_the_pending_chat(client: AsyncClient, app) -> None:
    email = _email()
    pending_id = await _pending_session(client, app, email)
    visitor = await _new_session_id(client)

    events = await chat_action(client, visitor, "resume_pending", {"email": email.upper()})
    assert token_text(events) == RESUME_PENDING_REPLY

    mail = _resume_mail(app, email)
    assert len(mail) == 1
    link = mail[0]["links"][0]
    token = parse_qs(urlparse(link).query)["t"][0]
    verified = await client.post("/api/verifications/email", json={"token": token})
    assert verified.status_code == 200, verified.text
    assert verified.json()["session_id"] == pending_id

    audit = app.state.services.audit.events(visitor)
    asked = [e for e in audit if e["type"] == "pending_resume_requested"]
    assert asked and asked[-1]["payload"] == {"found": True}


async def test_no_pending_inquiry_gets_the_same_reply_and_no_email(
    client: AsyncClient, app
) -> None:
    email = _email()
    visitor = await _new_session_id(client)
    events = await chat_action(client, visitor, "resume_pending", {"email": email})
    assert token_text(events) == RESUME_PENDING_REPLY
    assert _resume_mail(app, email) == []
    audit = app.state.services.audit.events(visitor)
    asked = [e for e in audit if e["type"] == "pending_resume_requested"]
    assert asked and asked[-1]["payload"] == {"found": False}


async def test_the_email_never_reaches_the_transcript_or_the_model(
    client: AsyncClient, app
) -> None:
    email = _email()
    await _pending_session(client, app, email)
    visitor = await _new_session_id(client)
    events = await chat_action(client, visitor, "resume_pending", {"email": email})
    assert "MODEL TURN" not in token_text(events)
    session = await app.state.session_store.get(visitor)
    assert email not in json.dumps(session.transcript)
    assert session.transcript[-1]["text"] == RESUME_PENDING_REPLY


async def test_an_expired_pending_inquiry_is_abandoned_not_resumed(
    client: AsyncClient, app
) -> None:
    email = _email()
    pending_id = await _pending_session(client, app, email)
    store = app.state.session_store
    session = await store.get(pending_id)
    repo = store.inquiry_repo
    inquiry = await repo.get(inquiry_id_for(session))
    old = datetime.now(tz=UTC) - timedelta(days=1)
    expired = await repo.expire_pending(old + timedelta(days=2), timedelta(minutes=120))
    assert inquiry.id in expired

    visitor = await _new_session_id(client)
    events = await chat_action(client, visitor, "resume_pending", {"email": email})
    assert token_text(events) == RESUME_PENDING_REPLY
    assert _resume_mail(app, email) == []
    assert (await repo.get(inquiry.id)).status == InquiryStatus.ABANDONED


async def test_not_an_email_is_handled_like_no_match(client: AsyncClient, app) -> None:
    visitor = await _new_session_id(client)
    events = await chat_action(client, visitor, "resume_pending", {"email": "not-an-email"})
    assert token_text(events) == RESUME_PENDING_REPLY
