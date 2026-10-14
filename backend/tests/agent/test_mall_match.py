from app.agent.mall_match import (
    extract_mall_phrases,
    phrase_matches_seed_mall,
    unmatched_mall_phrases,
)
from app.domain.master import load_master_data
from app.domain.models import FieldKey


def test_red_sea_mall_is_unmatched() -> None:
    master = load_master_data()
    text = "Bean Street kiosk at Red Sea Mall."
    assert "Red Sea Mall" in extract_mall_phrases(text)
    assert not phrase_matches_seed_mall("Red Sea Mall", master)
    assert unmatched_mall_phrases(text, master)


def test_riyadh_mall_a_matches_seed() -> None:
    master = load_master_data()
    text = "kiosk at Riyadh Mall A"
    assert phrase_matches_seed_mall("Riyadh Mall A", master)
    assert not unmatched_mall_phrases(text, master)


def test_generic_the_mall_phrases_ignored() -> None:
    master = load_master_data()
    assert not extract_mall_phrases("We want space in the mall.")
    assert not extract_mall_phrases("Something in your mall please.")
    assert not unmatched_mall_phrases("near the food court in the mall", master)


def test_riyadh_mall_a_among_generic_phrases() -> None:
    master = load_master_data()
    text = "in a mall in Riyadh, ideally Riyadh Mall A"
    phrases = extract_mall_phrases(text)
    assert "Riyadh Mall A" in phrases
    assert not unmatched_mall_phrases(text, master)


def test_user_selected_malls_not_cleared_for_generic_phrase() -> None:
    from app.agent.guard import _clear_malls_for_unknown_name
    from app.domain.draft_ops import new_inquiry_draft, write_fields
    from app.domain.models import Source
    from langchain_core.messages import AIMessage, HumanMessage

    master = load_master_data()
    draft = new_inquiry_draft()
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.MALLS.value, ["riyadh-mall-a"], Source.USER)],
        master=master,
    )
    user_text = "We'd like to be near the food court in the mall."
    messages = [HumanMessage(content=user_text), AIMessage(content="Noted.")]
    updated, note, cleared = _clear_malls_for_unknown_name(draft, user_text, master, messages)
    assert cleared is False
    assert updated.fields[FieldKey.MALLS].value == ["riyadh-mall-a"]
    assert note is None
