"""Chart S15: same CR and mall as an open inquiry (`duplicate_policy` in policy.yaml).

`warn` (shipped): one neutral notice card from code, then the inquiry can still be sent.
`block`: Submit is refused while the other inquiry is open. Found by the scenario-queries
live run (16 Nov): the policy had no code behind it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.agent.model import ScriptedChatModel
from app.api.cards import build_duplicate_notice_card
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey, InquiryDraft, Source
from app.policy.config import get_policy, use_policy
from app.workflow.duplicates import notice_card_id, open_duplicate
from app.workflow.models import Case, CaseStatus
from httpx import AsyncClient

from tests.scenarios.helpers import chat_action, chat_message, ui_cards

pytestmark = pytest.mark.intake_v2

T0 = datetime(2026, 11, 16, 9, tzinfo=UTC)
CR = "1010222222"


def _draft(cr: str | None = CR, malls: list[str] | None = None) -> InquiryDraft:
    draft = new_inquiry_draft()
    if cr is not None:
        draft.fields[FieldKey.CR_NUMBER].value = cr
        draft.fields[FieldKey.CR_NUMBER].source = Source.USER
    draft.fields[FieldKey.MALLS].value = malls if malls is not None else ["riyadh-mall-a"]
    draft.fields[FieldKey.MALLS].source = Source.USER
    return draft


def _case(
    reference: str = "GEO-STR-000201",
    *,
    status: CaseStatus = CaseStatus.FIRST_REVIEW,
    cr: str = CR,
    malls: list[str] | None = None,
    at: datetime = T0,
) -> Case:
    draft = _draft(cr, malls)
    draft.reference = reference
    return Case(
        id=reference,
        reference=reference,
        session_id=f"sess-{reference}",
        status=status,
        draft=draft,
        submitted_at=at,
    )


# ---- open_duplicate ---------------------------------------------------------------------


def test_same_cr_and_a_shared_mall_is_a_duplicate() -> None:
    found = open_duplicate([_case(malls=["riyadh-mall-a", "riyadh-mall-b"])], _draft())
    assert found is not None
    assert found.reference == "GEO-STR-000201"
    assert found.mall_ids == ("riyadh-mall-a",)


@pytest.mark.parametrize(
    ("case", "draft"),
    [
        (_case(malls=["jeddah-mall-a"]), _draft()),  # another mall
        (_case(cr="1010123456"), _draft()),  # another CR
        (_case(), _draft(cr=None)),  # CR skipped
        (_case(), _draft(malls=[])),  # no mall yet
        (_case(status=CaseStatus.REJECTED), _draft()),  # closed
        (_case(status=CaseStatus.SENT_TO_YARDI), _draft()),  # closed
    ],
)
def test_no_duplicate(case: Case, draft: InquiryDraft) -> None:
    assert open_duplicate([case], draft) is None


def test_the_cr_is_compared_by_digits_and_the_newest_open_case_wins() -> None:
    older = _case("GEO-STR-000201", at=T0)
    newer = _case("GEO-STR-000202", at=T0.replace(hour=10))
    found = open_duplicate([older, newer], _draft(cr="1010 222 222"))
    assert found is not None and found.reference == "GEO-STR-000202"


def test_a_case_is_not_its_own_duplicate() -> None:
    case = _case()
    assert open_duplicate([case], case.draft) is None


# ---- The notice card ----------------------------------------------------------------------


def test_the_notice_is_neutral_and_names_the_mall_and_reference() -> None:
    duplicate = open_duplicate([_case()], _draft())
    assert duplicate is not None
    card = build_duplicate_notice_card(duplicate, load_master_data())
    assert card.card_type == "duplicate_notice"
    assert card.card_id == notice_card_id(duplicate)
    message = card.payload["message"]
    assert "GEO-STR-000201" in message and "Riyadh Mall A" in message
    assert "You can still send this one" in message
    assert card.payload["policy"] == "warn"
    for word in ("duplicate", "error", "not allowed", "mistake"):
        assert word not in message.lower()


# ---- In the chat ----------------------------------------------------------------------------


@pytest.fixture
def model_factory():
    return lambda: ScriptedChatModel(steps=[{"content": "Noted."}] * 8)


async def _session_with(client: AsyncClient, app, draft: InquiryDraft) -> str:
    created = await client.post("/api/sessions")
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    store = app.state.session_store
    session = await store.get(session_id)
    merged = session.draft.model_copy(deep=True)
    merged.fields[FieldKey.CR_NUMBER] = draft.fields[FieldKey.CR_NUMBER]
    merged.fields[FieldKey.MALLS] = draft.fields[FieldKey.MALLS]
    session.draft = merged
    await store.save(session)
    return session_id


async def test_warn_shows_one_notice_then_never_again(client: AsyncClient, app) -> None:
    app.state.services.cases.save(_case())
    session_id = await _session_with(client, app, _draft())

    first = await chat_message(client, session_id, "Riyadh Mall A please")
    notices = ui_cards(first, "duplicate_notice")
    assert len(notices) == 1
    assert notices[0]["payload"]["reference"] == "GEO-STR-000201"

    second = await chat_message(client, session_id, "what's next?")
    assert ui_cards(second, "duplicate_notice") == []


async def test_no_notice_without_an_open_case(client: AsyncClient, app) -> None:
    app.state.services.cases.save(_case(status=CaseStatus.REJECTED))
    session_id = await _session_with(client, app, _draft())
    events = await chat_message(client, session_id, "Riyadh Mall A please")
    assert ui_cards(events, "duplicate_notice") == []


async def test_block_refuses_submit_while_the_other_is_open(client: AsyncClient, app) -> None:
    app.state.services.cases.save(_case())
    session_id = await _session_with(client, app, _draft())
    with use_policy(get_policy().with_changes(duplicate_policy="block")):
        events = await chat_action(
            client, session_id, "accept_and_submit", {"terms_accepted": True}
        )
    notices = ui_cards(events, "duplicate_notice")
    assert len(notices) == 1 and notices[0]["payload"]["policy"] == "block"
    assert ui_cards(events, "success") == []
    session = await app.state.session_store.get(session_id)
    assert session.draft.reference is None
