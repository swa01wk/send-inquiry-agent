from app.agent.brand_infer import fill_brands_from_user_message
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


def test_brand_reask_note_when_paren_brand_in_user_message() -> None:
    draft = new_inquiry_draft()
    user_text = "Bean Street (بين ستريت) café at Riyadh Mall A"
    messages = [
        HumanMessage(content=user_text),
        AIMessage(content="What is your brand name?"),
    ]
    state = _state(draft, messages)
    note = _brand_reask_note(state, "What is your brand name?")
    assert note is not None


def test_incomplete_bulk_skips_brand_when_paren_in_message() -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    user_text = (
        "Acme Trading LLC on King Abdullah Road. Bean Street (بين ستريت) specialty café "
        "at Riyadh Mall A — Sara Ali, sara@beanstreet.example, +966501234567."
    )
    draft, _ = fill_brands_from_user_message(draft, user_text)
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.UNIT_TYPE.value, "specialty", Source.USER),
            (FieldKey.EMAIL.value, "sara@beanstreet.example", Source.USER),
            (FieldKey.MOBILE.value, "+966501234567", Source.USER),
        ],
        master=load_master_data(),
    )
    messages = [
        HumanMessage(content=user_text),
        AIMessage(
            content="",
            tool_calls=[{"name": "update_draft", "args": {}, "id": "1", "type": "tool_call"}],
        ),
        AIMessage(content="Thanks."),
    ]
    state = _state(draft, messages)
    assert _incomplete_bulk_capture_note(state, "collecting") is None


def test_brand_reask_note_not_on_arabic_brand_statement() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER)],
        master=master,
    )
    state = _state(draft, [])
    assert _brand_reask_note(state, "Please share your Arabic brand name next.") is None


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


def _kiosk_bundle_state(messages):
    # The upload path's bundle: space and contact, no brand (the Brand Profile gives it).
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    draft, _, _ = write_fields(
        draft,
        [
            (FieldKey.UNIT_TYPE.value, "specialty", Source.DERIVED),
            (FieldKey.EMAIL.value, "sara@beanstreet.example", Source.USER),
            (FieldKey.MOBILE.value, "+966501234567", Source.USER),
        ],
        master=load_master_data(),
    )
    bundle = (
        "Specialty coffee kiosk at Riyadh Mall A. Sara Ali, sara@beanstreet.example, 0501234567"
    )
    tool_call = {"name": "update_draft", "args": {"fields": []}, "id": "t1", "type": "tool_call"}
    return _state(
        draft,
        [
            *messages,
            HumanMessage(content=bundle),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="Thanks, Sara."),
        ],
    )


def test_incomplete_bulk_still_asks_for_the_brand_on_a_typed_bundle() -> None:
    state = _kiosk_bundle_state([HumanMessage(content="I'll type them")])
    note = _incomplete_bulk_capture_note(state, "collecting")
    assert note is not None and "brand_name_en" in note


def test_incomplete_bulk_skips_the_brand_when_the_profiles_are_coming() -> None:
    # Demo feedback §3.7, live eval 9 Nov: the guard made the model invent a brand.
    state = _kiosk_bundle_state([HumanMessage(content="I'll upload the profiles")])
    assert _incomplete_bulk_capture_note(state, "collecting") is None


def test_brand_reask_note_not_when_asking_for_the_missing_arabic_name() -> None:
    """R4: after the Brand Profile fills the English name, asking for the Arabic one is fine;
    asking again once it's known is still a re-ask."""
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(),
        [(FieldKey.BRAND_NAME_EN.value, "Oasis Bakehouse", Source.DERIVED)],
        master=master,
        evidence={
            "brand_name_en": "Brand Profile: new_brand_profile.pdf, uploaded 09 Nov 2026 18:00"
        },
    )
    state = _state(draft, [])
    assert _brand_reask_note(state, "Thanks. What's the brand name in Arabic?") is None
    draft, _, _ = write_fields(
        draft, [(FieldKey.BRAND_NAME_AR.value, "مخبز الواحة", Source.USER)], master=master
    )
    assert _brand_reask_note(_state(draft, []), "What's the brand name in Arabic?") is not None


def test_brand_reask_note_still_on_an_arabic_ask_for_a_typed_brand() -> None:
    """A typed or dictated Latin brand: the model proposes the Arabic name itself, so asking
    for it is still a re-ask (live eval "channels: dictated caller", 10 Nov)."""
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(),
        [(FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.USER)],
        master=master,
    )
    assert _brand_reask_note(_state(draft, []), "What's the brand name in Arabic?") is not None
