"""Value buttons on `confirm_fields` rows (18 Nov B1, M27, NG3).

A tap sends `confirm_field {card_id, key}` and confirms that field only. While other rows on
the card still wait it is quiet; the last open row runs the agent turn, so a card costs one
turn as "Looks right" did. Old sessions may still send `confirm_card`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey, FieldValue, Source
from httpx import AsyncClient
from tests.domain.conftest import fill_minimal_collectible

_CARD = "confirm-1"
_KEYS = ["sales_category", "brand_name_ar"]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        session_ttl_minutes=120,
        dev_tools=True,
        token_secret="test-secret",
    )


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Thanks."}] * 4)


async def _action(client: AsyncClient, session_id: str, action: str, payload: dict) -> list:
    body = {"type": "action", "action": action, "payload": payload}
    events: list[tuple[str, dict]] = []
    async with client.stream("POST", f"/api/sessions/{session_id}/chat", json=body) as response:
        assert response.status_code == 200
        current: str | None = None
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                current = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current:
                events.append((current, json.loads(line.split(":", 1)[1].strip())))
    return events


async def _notes(app, session_id: str) -> list[str]:
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    return [
        str(m.content)
        for m in (snapshot.values or {}).get("messages", [])
        if str(m.content).startswith("[ui_event]")
    ]


async def _session_with_card(client: AsyncClient, app):
    created = await client.post("/api/sessions")
    session = await app.state.session_store.get(created.json()["session_id"])
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe", source=Source.DERIVED, evidence="coffee"
    )
    draft.fields[FieldKey.BRAND_NAME_AR] = FieldValue(
        value="بين ستريت", source=Source.DERIVED, evidence="Bean Street"
    )
    session.draft = draft
    session.confirm_card_keys[_CARD] = list(_KEYS)
    return session


def _card(events: list) -> dict:
    return [d for n, d in events if n == "ui_card" and d["card_type"] == "confirm_fields"][-1]


@pytest.mark.asyncio
async def test_each_tap_confirms_one_field_and_the_last_runs_the_turn(client, app) -> None:
    session = await _session_with_card(client, app)

    first = await _action(client, session.id, "confirm_field", {"card_id": _CARD, "key": _KEYS[0]})

    assert "token" not in [n for n, _ in first]
    assert session.draft.fields[FieldKey.SALES_CATEGORY].confirmed
    assert not session.draft.fields[FieldKey.BRAND_NAME_AR].confirmed
    rows = {r["key"]: r for r in _card(first)["payload"]["fields"]}
    assert rows["sales_category"]["confirmed"] and not rows["brand_name_ar"]["confirmed"]
    assert rows["brand_name_ar"]["value_label"] == "بين ستريت"
    assert await _notes(app, session.id) == []

    last = await _action(client, session.id, "confirm_field", {"card_id": _CARD, "key": _KEYS[1]})

    assert "token" in [n for n, _ in last]
    assert _card(last)["payload"]["all_confirmed"] is True
    assert await _notes(app, session.id) == [
        "[ui_event] fields_confirmed sales_category brand_name_ar"
    ]


@pytest.mark.asyncio
async def test_a_key_not_on_the_card_or_a_stale_card_confirms_nothing(client, app) -> None:
    session = await _session_with_card(client, app)

    await _action(client, session.id, "confirm_field", {"card_id": _CARD, "key": "email"})
    await _action(client, session.id, "confirm_field", {"card_id": f"{_CARD}~2", "key": _KEYS[0]})

    assert not session.draft.fields[FieldKey.SALES_CATEGORY].confirmed
    assert all(n.startswith("[ui_event] confirm_failed") for n in await _notes(app, session.id))


@pytest.mark.asyncio
async def test_a_tap_on_a_confirmed_row_is_quiet(client, app) -> None:
    session = await _session_with_card(client, app)
    await _action(client, session.id, "confirm_field", {"card_id": _CARD, "key": _KEYS[0]})

    again = await _action(client, session.id, "confirm_field", {"card_id": _CARD, "key": _KEYS[0]})

    assert "token" not in [n for n, _ in again]
    assert await _notes(app, session.id) == []


@pytest.mark.asyncio
async def test_confirm_card_still_confirms_the_whole_card(client, app) -> None:
    session = await _session_with_card(client, app)

    await _action(client, session.id, "confirm_card", {"card_id": _CARD})

    assert all(session.draft.fields[FieldKey(k)].confirmed for k in _KEYS)
