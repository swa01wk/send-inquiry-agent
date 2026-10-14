from app.agent.guard import _clear_malls_for_unknown_name
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from langchain_core.messages import AIMessage, HumanMessage


def test_clears_malls_when_user_named_unknown_mall() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.MALLS.value, ["riyadh-mall-a"], Source.DERIVED)],
        master=master,
    )
    user_text = "Bean Street kiosk at Red Sea Mall."
    messages = [
        HumanMessage(content=user_text),
        AIMessage(content="Noted."),
    ]
    updated, note, cleared = _clear_malls_for_unknown_name(draft, user_text, master, messages)
    assert cleared is True
    assert updated.fields[FieldKey.MALLS].value == []
    assert note is not None
