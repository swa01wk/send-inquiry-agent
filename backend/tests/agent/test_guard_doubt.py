from app.agent.guard import _unconfirm_doubted_fields
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft
from app.domain.models import FieldKey, FieldValue, Source
from app.domain.rules import compute_phase
from langchain_core.messages import HumanMessage


def test_unconfirm_sales_category_on_category_doubt() -> None:
    draft = new_inquiry_draft()
    draft.fields[FieldKey.SALES_CATEGORY] = FieldValue(
        value="fnb_cafe",
        source=Source.DERIVED,
        confirmed=True,
    )
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="s1", draft=draft, phase=phase)
    state["messages"] = [
        HumanMessage(content="Hmm, not sure about the category"),
        HumanMessage(content="[ui_event] ignored"),
    ]
    # _current_turn uses last non-guard human - need only one human
    state["messages"] = [HumanMessage(content="Hmm, not sure about the category")]
    updated, changed = _unconfirm_doubted_fields(state)
    assert "sales_category" in changed
    assert updated.fields[FieldKey.SALES_CATEGORY].confirmed is False
