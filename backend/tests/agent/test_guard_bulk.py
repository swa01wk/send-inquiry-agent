from app.agent.guard import _brand_reask_note, _incomplete_bulk_capture_note
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.domain.rules import compute_phase
from langchain_core.messages import AIMessage, HumanMessage


def _state(draft, messages):
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="s1", draft=draft, phase=phase)
    state["messages"] = messages
    return state


def test_brand_reask_note_when_brand_already_known() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER)],
        master=master,
    )
    state = _state(draft, [])
    note = _brand_reask_note(state, "What is your brand name?")
    assert note is not None
    assert "brand name" in note.lower()


def test_incomplete_bulk_capture_after_partial_update() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    user_text = (
        "Acme Trading LLC on King Abdullah Road. Bean Street (بين ستريت) specialty café "
        "at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567."
    )
    messages = [
        HumanMessage(content=user_text),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "update_draft",
                    "args": {},
                    "id": "1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="Thanks, almost done."),
    ]
    state = _state(draft, messages)
    note = _incomplete_bulk_capture_note(state, "collecting")
    assert note is not None
    assert "brand_name_en" in note
