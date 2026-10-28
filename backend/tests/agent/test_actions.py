from datetime import UTC, datetime

import pytest
from app.agent.actions import handle_ui_action
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, Source
from app.sessions import Session


@pytest.mark.asyncio
async def test_confirm_card_only_confirms_listed_fields(agent_runtime) -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "new"
    draft.fields[FieldKey.COMPANY_NAME] = draft.fields[FieldKey.COMPANY_NAME].model_copy(
        update={"value": "Acme LLC", "source": Source.VERIFIED, "confirmed": False},
    )
    draft.fields[FieldKey.BRAND_NAME_AR] = draft.fields[FieldKey.BRAND_NAME_AR].model_copy(
        update={"value": "أكme", "source": Source.DERIVED, "confirmed": False},
    )
    now = datetime.now(tz=UTC)
    session = Session(id="sess-confirm", draft=draft, created_at=now, last_seen=now)
    session.confirm_card_keys["confirm-1"] = [FieldKey.COMPANY_NAME.value]

    result = await handle_ui_action(
        "confirm_card",
        {"card_id": "confirm-1"},
        session,
        agent_runtime,
    )

    assert session.draft.fields[FieldKey.COMPANY_NAME].confirmed is True
    assert session.draft.fields[FieldKey.BRAND_NAME_AR].confirmed is False
    assert "company_name" in result.note.content


@pytest.mark.asyncio
async def test_confirm_card_already_confirmed_is_not_a_failure(agent_runtime) -> None:
    # The agent confirmed from the user's "yes"; the user then taps "Looks right" too.
    draft = new_inquiry_draft()
    draft.cr_status = "new"
    draft.fields[FieldKey.COMPANY_NAME] = draft.fields[FieldKey.COMPANY_NAME].model_copy(
        update={"value": "Acme LLC", "source": Source.VERIFIED, "confirmed": True},
    )
    now = datetime.now(tz=UTC)
    session = Session(id="sess-confirmed", draft=draft, created_at=now, last_seen=now)
    session.confirm_card_keys["confirm-1"] = [FieldKey.COMPANY_NAME.value]

    result = await handle_ui_action(
        "confirm_card", {"card_id": "confirm-1"}, session, agent_runtime
    )

    assert result.note.content == "[ui_event] fields_already_confirmed"
    cards = [e["data"] for e in result.events if e["event"] == "ui_card"]
    assert cards and cards[0]["payload"]["all_confirmed"] is True


@pytest.mark.asyncio
async def test_unknown_confirm_card_still_fails(agent_runtime) -> None:
    now = datetime.now(tz=UTC)
    session = Session(id="sess-x", draft=new_inquiry_draft(), created_at=now, last_seen=now)
    result = await handle_ui_action(
        "confirm_card", {"card_id": "confirm-9"}, session, agent_runtime
    )
    assert result.note.content == "[ui_event] confirm_failed"
