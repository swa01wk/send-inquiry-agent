"""The `choice` card's options (18 Nov B1 §3.2, NG2, ADR-N2).

A tap sends `choose_option {card_id, key, value}`: the value must be on the open card, and
it is written as the user's own answer (`source: user`, confirmed). Typing exactly one
option's name does the same.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.agent.model import ScriptedChatModel
from app.api.cards import build_choice_card, category_options
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey, FieldValue, Source
from httpx import AsyncClient
from tests.domain.conftest import fill_minimal_collectible


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


async def _read_sse(response) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current: str | None = None
    async for line in response.aiter_lines():
        if line.startswith("event:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current:
            events.append((current, json.loads(line.split(":", 1)[1].strip())))
    return events


async def _post(client: AsyncClient, session_id: str, body: dict) -> tuple[int, list]:
    async with client.stream("POST", f"/api/sessions/{session_id}/chat", json=body) as response:
        if response.status_code != 200:
            await response.aread()
            return response.status_code, []
        return 200, await _read_sse(response)


async def _notes(app, session_id: str) -> list[str]:
    snapshot = await app.state.graph.aget_state({"configurable": {"thread_id": session_id}})
    return [
        str(m.content)
        for m in (snapshot.values or {}).get("messages", [])
        if "[ui_event]" in str(m.content)
    ]


async def _session_with_options(client: AsyncClient, app, *, lang: str = "en"):
    created = await client.post("/api/sessions")
    session = await app.state.session_store.get(created.json()["session_id"])
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue()
    session.draft = draft
    card = build_choice_card(
        "sales_category", category_options(master, ["fnb_cafe", "fnb_restaurant"]), lang=lang
    )
    session.remember_card(card.model_dump())
    return session


def _action(card_id: str, value: str, key: str = "sales_category") -> dict:
    return {
        "type": "action",
        "action": "choose_option",
        "payload": {"card_id": card_id, "key": key, "value": value},
    }


@pytest.mark.asyncio
async def test_a_tap_writes_the_users_own_answer(client, app) -> None:
    session = await _session_with_options(client, app)

    status, events = await _post(client, session.id, _action("choice-sales_category", "fnb_cafe"))

    assert status == 200
    field = session.draft.fields[FieldKey.SALES_CATEGORY]
    assert (field.value, field.source, field.confirmed) == ("fnb_cafe", Source.USER, True)
    card = [d for n, d in events if n == "ui_card" and d["card_type"] == "choice"][-1]
    assert card["payload"]["chosen"] == "fnb_cafe"
    assert "[ui_event] option_chosen sales_category=fnb_cafe" in await _notes(app, session.id)


@pytest.mark.asyncio
async def test_a_value_that_is_not_on_the_card_is_refused(client, app) -> None:
    session = await _session_with_options(client, app)

    status, _ = await _post(client, session.id, _action("choice-sales_category", "fashion"))

    assert status == 409
    assert session.draft.fields[FieldKey.SALES_CATEGORY].value is None


@pytest.mark.asyncio
async def test_an_unknown_or_answered_card_is_refused(client, app) -> None:
    session = await _session_with_options(client, app)

    unknown, _ = await _post(client, session.id, _action("choice-malls", "fnb_cafe"))
    first, _ = await _post(client, session.id, _action("choice-sales_category", "fnb_cafe"))
    again, _ = await _post(client, session.id, _action("choice-sales_category", "fnb_restaurant"))

    assert (unknown, first, again) == (409, 200, 409)
    assert session.draft.fields[FieldKey.SALES_CATEGORY].value == "fnb_cafe"


@pytest.mark.asyncio
async def test_a_tap_on_a_derived_value_makes_it_the_users(client, app) -> None:
    session = await _session_with_options(client, app)
    session.draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe", source=Source.DERIVED, confirmed=False, evidence="coffee"
    )

    status, _ = await _post(client, session.id, _action("choice-sales_category", "fnb_cafe"))

    assert status == 200
    field = session.draft.fields[FieldKey.SALES_CATEGORY]
    assert (field.source, field.confirmed, field.evidence) == (Source.USER, True, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("typed", ["Café", "café.", "مقهى", "Food & Beverage · Café"])
async def test_typing_one_options_name_is_the_same_as_a_tap(client, app, typed: str) -> None:
    session = await _session_with_options(client, app)

    status, _ = await _post(client, session.id, {"type": "message", "text": typed})

    assert status == 200
    field = session.draft.fields[FieldKey.SALES_CATEGORY]
    assert (field.value, field.source) == ("fnb_cafe", Source.USER)
    notes = await _notes(app, session.id)
    assert any(n.endswith("[ui_event] option_chosen sales_category=fnb_cafe") for n in notes)


@pytest.mark.asyncio
async def test_typing_something_else_is_an_ordinary_message(client, app) -> None:
    session = await _session_with_options(client, app)

    status, _ = await _post(client, session.id, {"type": "message", "text": "a café, I think"})

    assert status == 200
    assert session.draft.fields[FieldKey.SALES_CATEGORY].value is None
    assert session.cards["choice-sales_category"]["payload"]["chosen"] is None
