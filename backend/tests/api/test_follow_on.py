"""Follow-on inquiries: a second mall reuses the verified details (L3 §3.11)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.api.cards import scope_card_data, scoped_card_id, split_card_id
from app.config import Settings
from app.domain.draft_ops import follow_on_draft
from app.domain.models import DocType, FieldKey, Source
from app.domain.rules import can_submit
from tests.scenarios.helpers import (
    chat_action,
    chat_message,
    last_draft,
    ready_to_submit_draft,
    scenario_client,
    ui_cards,
)

FOLLOW_ON_STEPS = [
    {"content": "Thank you, it's on its way to our leasing team."},
    {
        "content": "",
        "tool_calls": [
            {
                "name": "start_follow_on",
                "args": {"mall_id": "riyadh-mall-b"},
                "id": "fo1",
                "type": "tool_call",
            }
        ],
    },
    {"content": "Happy to. I've copied your details; please confirm them on the card."},
    {"content": "All set. Accept the terms and submit when you're ready."},
    {"content": "Thank you!"},
    {"content": "OK"},
]


@pytest.fixture
def fo_settings(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"), dev_tools=True, token_secret="t")


async def _submitted_session(client, app, *, verified_hours_ago: float = 1.0) -> str:
    created = await client.post("/api/sessions")
    session_id = created.json()["session_id"]
    session = await app.state.session_store.get(session_id)
    draft = ready_to_submit_draft(app)
    draft.verified_at = datetime.now(tz=UTC) - timedelta(hours=verified_hours_ago)
    session.draft = draft
    events = await chat_action(client, session_id, "accept_and_submit", {"terms_accepted": True})
    assert ui_cards(events, "success")
    return session_id


async def test_second_mall_in_two_messages(fo_settings) -> None:
    async with scenario_client(fo_settings, FOLLOW_ON_STEPS) as (client, app):
        session_id = await _submitted_session(client, app)
        session = await app.state.session_store.get(session_id)
        first_ref = session.draft.reference
        assert first_ref

        events = await chat_message(client, session_id, "Can we also do Riyadh Mall B?")
        cards = ui_cards(events, "confirm_fields")
        assert len(cards) == 1
        card = cards[0]
        assert card["card_id"] == "confirm-1~2"
        assert card["payload"]["title"] == f"Same details as {first_ref}"
        keys = [row["key"] for row in card["payload"]["fields"]]
        assert {"company_name", "brand_name_en", "unit_type", "sales_category", "email"} <= set(
            keys
        )
        assert all(row["source"] == "verified" for row in card["payload"]["fields"])
        assert last_draft(events)["follow_on_of"] == first_ref

        assert session.inquiry_seq == 2
        draft = session.draft
        assert draft.reference is None
        assert draft.follow_on_of == first_ref
        assert draft.fields[FieldKey.MALLS].value == ["riyadh-mall-b"]
        assert draft.email_verified and draft.mobile_verified  # verified an hour ago
        assert {d.value for d in draft.documents} == {"company_profile", "brand_profile"}
        assert all(d.copied_from == first_ref for d in draft.documents.values())

        # A card from the first inquiry can't change the new one.
        stale = await chat_action(client, session_id, "confirm_card", {"card_id": "confirm-1"})
        assert not ui_cards(stale, "confirm_fields")

        # One click confirms everything; the review card comes next, scoped to inquiry 2.
        confirmed = await chat_action(
            client, session_id, "confirm_card", {"card_id": card["card_id"]}
        )
        assert ui_cards(confirmed, "confirm_fields")[0]["payload"]["all_confirmed"] is True
        review = ui_cards(confirmed, "review")
        assert review and review[0]["card_id"] == "review~2"

        submitted = await chat_action(
            client, session_id, "accept_and_submit", {"terms_accepted": True}
        )
        success = ui_cards(submitted, "success")[0]
        assert success["card_id"] == "success~2"
        second_ref = success["payload"]["reference"]
        assert second_ref != first_ref
        assert len(app.state.services.submit.submissions) == 2
        assert app.state.services.submit.lookup(f"inq:{session_id}:v2") == second_ref
        assert app.state.services.submit.submissions[second_ref]["follow_on_of"] == first_ref

        audit = (await client.get(f"/api/dev/audit/{session_id}")).json()["events"]
        started = [e for e in audit if e["type"] == "follow_on_started"]
        assert started[0]["payload"] == {
            "from_reference": first_ref,
            "inquiry_seq": 2,
            "reused_verification": True,
        }

        # Resume shows both inquiries' cards.
        resumed_ids = set(session.cards)
        assert {"success", "success~2", "confirm-1~2"} <= resumed_ids


async def test_deleting_a_reused_document_keeps_the_original_file(fo_settings, monkeypatch) -> None:
    async with scenario_client(fo_settings, FOLLOW_ON_STEPS) as (client, app):
        session_id = await _submitted_session(client, app)
        await chat_message(client, session_id, "Can we also do Riyadh Mall B?")
        deleted: list[str] = []
        monkeypatch.setattr(
            app.state.services.storage, "delete", lambda sid, doc, fid: deleted.append(fid)
        )
        response = await client.delete(f"/api/sessions/{session_id}/documents/company_profile")
        assert response.status_code == 200
        assert response.json()["card"]["card_id"] == "documents~2"
        assert deleted == []
        session = await app.state.session_store.get(session_id)
        assert DocType.COMPANY_PROFILE not in session.draft.documents


# ---- follow_on_draft (domain) ----------------------------------------------------------


def _submitted_draft(app_like, verified_at):
    from types import SimpleNamespace

    draft = ready_to_submit_draft(SimpleNamespace(state=SimpleNamespace(settings=app_like)))
    draft.reference = "GEO-STR-111111"
    draft.terms_accepted = True
    draft.verified_at = verified_at
    return draft


def test_follow_on_draft_copies_and_reuses_recent_verification(fo_settings) -> None:
    now = datetime(2026, 10, 29, 12, tzinfo=UTC)
    previous = _submitted_draft(fo_settings, now - timedelta(hours=2))
    draft, copied, reused = follow_on_draft(previous, reuse_hours=24, now=now)
    assert reused
    assert draft.email_verified and draft.mobile_verified
    assert draft.follow_on_of == "GEO-STR-111111"
    assert draft.reference is None and not draft.terms_accepted
    assert draft.fields[FieldKey.MALLS].value is None
    assert draft.fields[FieldKey.AREA_MIN].source == Source.DEFAULT
    for key in copied:
        field = draft.fields[FieldKey(key)]
        assert field.source == Source.VERIFIED and field.confirmed is False
    assert "malls" not in copied
    blockers = {b.token for b in can_submit(draft)}
    assert "missing_field:malls" in blockers
    assert "unconfirmed_field:company_name" in blockers
    assert "email_not_verified" not in blockers


def test_follow_on_draft_asks_to_verify_again_after_the_window(fo_settings) -> None:
    now = datetime(2026, 10, 29, 12, tzinfo=UTC)
    previous = _submitted_draft(fo_settings, now - timedelta(hours=30))
    draft, _copied, reused = follow_on_draft(previous, reuse_hours=24, now=now)
    assert not reused
    assert not draft.email_verified and not draft.mobile_verified
    assert draft.email_link_sent_to is None and draft.verified_at is None


# ---- card ids per inquiry --------------------------------------------------------------


def test_card_id_scoping_round_trip() -> None:
    assert scoped_card_id("review", 1) == "review"
    assert scoped_card_id("review", 3) == "review~3"
    assert split_card_id("confirm-2~3") == ("confirm-2", 3)
    assert split_card_id("confirm-2") == ("confirm-2", 1)
    assert split_card_id("odd~name") == ("odd~name", 1)
    data = {"card_id": "documents~2", "card_type": "document_upload"}
    assert scope_card_data(data, 3)["card_id"] == "documents~3"
    assert scope_card_data({"card_id": "review"}, 1) == {"card_id": "review"}
