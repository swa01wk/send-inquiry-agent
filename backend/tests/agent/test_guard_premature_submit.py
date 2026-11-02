"""Guard: no "last step" or Submit talk while verification or documents are still open.

Nov 2026 manual test: the user uploaded documents before opening the email link; the agent
replied "Thanks, everything's in… review card" and later "You're at the last step now".
"""

from datetime import UTC, datetime

import pytest
from app.agent.graph import build_graph
from app.agent.guard import GUARD_PREFIX, _premature_submit_note
from app.agent.model import ScriptedChatModel
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import add_document, new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import DocType
from app.domain.rules import compute_phase
from langchain_core.messages import AIMessage, HumanMessage
from tests.domain.conftest import fill_minimal_collectible


def _documents_in_email_open():
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.mobile_verified = True
    for doc_type, file_id in ((DocType.COMPANY_PROFILE, "co-1"), (DocType.BRAND_PROFILE, "br-1")):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=f"{file_id}.pdf",
            size_bytes=100,
            max_bytes=5 * 1024 * 1024,
            uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    return draft


@pytest.mark.parametrize(
    "reply",
    [
        # The replies from the manual test.
        "Thanks, everything’s in. I’m pointing you to the review card now, where you can "
        "check the details, accept the terms, and submit when ready.",
        "Your mobile is verified now. You can carry on with the review card and submit when "
        "you’re ready.",
        "You’re at the last step now: check the review card, accept the terms, and press Submit.",
        "I can’t click or send it for you, but the Submit button is in the review card. Tick "
        "the terms box there, then press Submit when you’re ready.",
    ],
)
def test_submit_talk_with_the_email_link_open_is_retried(reply: str) -> None:
    note = _premature_submit_note({}, _documents_in_email_open(), reply)
    assert note is not None
    assert note.startswith(GUARD_PREFIX)
    assert "the email link" in note


@pytest.mark.parametrize(
    "reply",
    [
        "Your documents are in. Open the email link we sent you and the review card will follow.",
        "Nearly there — the last thing is the verification link in your email.",
        "Thanks — noted.",
    ],
)
def test_naming_what_is_open_is_fine(reply: str) -> None:
    assert _premature_submit_note({}, _documents_in_email_open(), reply) is None


def test_only_terms_left_may_point_to_submit() -> None:
    draft = _documents_in_email_open()
    draft.email_verified = True
    reply = "You're at the last step: tick the terms on the review card and press Submit."
    assert _premature_submit_note({}, draft, reply) is None


def test_not_applied_while_collecting_or_in_assisted_mode() -> None:
    collecting = new_inquiry_draft()
    collecting.cr_status = "skipped"
    reply = "Everything's in — press Submit on the review card."
    assert _premature_submit_note({}, collecting, reply) is None
    assert _premature_submit_note({"assisted": True}, _documents_in_email_open(), reply) is None


@pytest.mark.asyncio
async def test_graph_retries_premature_submit_once(agent_runtime: AgentRuntime) -> None:
    draft = _documents_in_email_open()
    state = initial_agent_state(
        session_id="sess-premature", draft=draft, phase=compute_phase(draft).value
    )
    second = "Your documents are in. The last thing before Submit is the email link we sent you."
    model = ScriptedChatModel(
        steps=[
            {"content": "Thanks, everything's in. Check the review card and press Submit."},
            {"content": second},
        ]
    )
    graph = build_graph(model_factory=lambda: model)
    config = {"configurable": {"thread_id": "sess-premature", "runtime": agent_runtime}}
    result = await graph.ainvoke(
        {
            **state,
            "messages": [
                HumanMessage(content="[ui_event] documents_complete still_needed=verify_email")
            ],
        },
        config=config,
    )
    assert result["guard_retries"] == 1
    replies = [m.content for m in result["messages"] if isinstance(m, AIMessage)]
    assert replies[-1] == second
