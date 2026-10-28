"""Chat endpoint routing integration (contact lines, handoff)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.agent.graph import build_graph
from app.agent.model import ScriptedChatModel
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from tests.scenarios.agent_steps import say, tool_step
from tests.scenarios.helpers import chat_message, ui_cards


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        upload_dir=str(tmp_path / "uploads"),
        max_upload_mb=5,
        agent_mode="scripted",
        dev_tools=True,
    )


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(
        steps=[
            tool_step(
                "update_draft",
                {
                    "fields": [
                        {"key": "first_name", "value": "Sara", "source": "user"},
                        {"key": "last_name", "value": "Ali", "source": "user"},
                        {"key": "contact_number", "value": "0501234567", "source": "user"},
                    ]
                },
                "c1",
            ),
            say("Thanks, Sara — I've saved your contact details."),
        ]
    )


async def _session(client) -> str:
    created = await client.post("/api/sessions")
    return created.json()["session_id"]


async def _seed_collecting(app, session_id: str) -> None:
    store = app.state.session_store
    session = await store.get(session_id)
    master = load_master_data()
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER),
            (FieldKey.MALLS.value, ["riyadh-mall-a"], Source.USER),
        ],
        master=master,
    )
    session.draft = draft
    store.save(session)


@pytest.mark.asyncio
async def test_call_me_mid_intake_saves_contact_not_handoff(client, app, model_factory) -> None:
    app.state.graph = build_graph(model_factory=model_factory)
    session_id = await _session(client)
    await _seed_collecting(app, session_id)

    events = await chat_message(client, session_id, "Sara Ali, call me on 0501234567")
    assert not ui_cards(events, "handoff")

    session = await app.state.session_store.get(session_id)
    assert session.draft.fields[FieldKey.FIRST_NAME].value == "Sara"
    assert session.draft.fields[FieldKey.MOBILE].value is not None
