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
