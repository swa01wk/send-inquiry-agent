from app.agent.mall_match import (
    extract_mall_phrases,
    fill_mentioned_malls,
    filter_mall_ids,
    mentioned_seed_mall_ids,
    phrase_matches_seed_mall,
    unknown_mall_phrases,
    user_message_mentions_mall,
)
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from app.domain.models import FieldKey


def test_mentioned_seed_mall_ids_mall_of_arabia() -> None:
    master = load_master_data()
    text = "We're opening a Zara Home store at Mall of Arabia."
    assert mentioned_seed_mall_ids(text, master) == ["mall-of-arabia"]


def test_fill_mentioned_malls_on_empty_draft() -> None:
    master = load_master_data()
    draft = new_inquiry_draft()
    text = "We're opening a Zara Home store at Mall of Arabia."
    updated, filled = fill_mentioned_malls(draft, text, master)
    assert filled is True
    assert updated.fields[FieldKey.MALLS].value == ["mall-of-arabia"]


def test_mall_of_arabia_mentioned() -> None:
    master = load_master_data()
    accepted, rejected = filter_mall_ids(
        ["mall-of-arabia"],
        [],
        "We're at Mall of Arabia",
        master,
    )
    assert accepted == ["mall-of-arabia"]
    assert not rejected


def test_red_sea_mall_not_accepted() -> None:
    master = load_master_data()
    text = "Bean Street kiosk at Red Sea Mall."
    assert "Red Sea Mall" in extract_mall_phrases(text)
    assert not phrase_matches_seed_mall("Red Sea Mall", master)
    assert unknown_mall_phrases(text, master)
    accepted, rejected = filter_mall_ids(
        ["riyadh-mall-a"],
        [],
        text,
        master,
    )
    assert accepted == []
    assert rejected == ["riyadh-mall-a"]


def test_generic_the_mall_phrases_ignored() -> None:
    master = load_master_data()
    assert not extract_mall_phrases("We want space in the mall.")
    assert not extract_mall_phrases("Something in your mall please.")
    assert not unknown_mall_phrases("near the food court in the mall", master)


def test_existing_picker_selection_kept_on_generic_phrase() -> None:
    master = load_master_data()
    accepted, rejected = filter_mall_ids(
        ["riyadh-mall-a"],
        ["riyadh-mall-a"],
        "We'd like to be near the food court in the mall.",
        master,
    )
    assert accepted == ["riyadh-mall-a"]
    assert not rejected


def test_riyadh_mall_a_or_red_sea_only_riyadh() -> None:
    master = load_master_data()
    text = "Riyadh Mall A or Red Sea Mall"
    assert user_message_mentions_mall(text, "Riyadh Mall A")
    accepted, rejected = filter_mall_ids(
        ["riyadh-mall-a", "jeddah-mall-a"],
        [],
        text,
        master,
    )
    assert accepted == ["riyadh-mall-a"]
    assert rejected == ["jeddah-mall-a"]


def test_riyadh_mall_a_among_generic_phrases() -> None:
    master = load_master_data()
    text = "in a mall in Riyadh, ideally Riyadh Mall A"
    phrases = extract_mall_phrases(text)
    assert "Riyadh Mall A" in phrases
    assert not unknown_mall_phrases(text, master)


def test_city_only_riyadh_does_not_match_malls() -> None:
    master = load_master_data()
    text = "somewhere in Riyadh"
    assert mentioned_seed_mall_ids(text, master) == []


def test_at_riyadh_mall_a_only_that_mall() -> None:
    master = load_master_data()
    text = "at Riyadh Mall A"
    assert mentioned_seed_mall_ids(text, master) == ["riyadh-mall-a"]


def test_saudi_arabia_brand_does_not_match_mall_of_arabia() -> None:
    master = load_master_data()
    text = "Saudi Arabia based brand"
    assert mentioned_seed_mall_ids(text, master) == []


def test_jeddah_office_riyadh_want_matches_no_malls() -> None:
    master = load_master_data()
    text = "office in Jeddah but we want Riyadh"
    assert mentioned_seed_mall_ids(text, master) == []


def test_mall_of_arabia_with_optional_the() -> None:
    master = load_master_data()
    for text in ("at Mall of Arabia", "at the Mall of Arabia"):
        assert mentioned_seed_mall_ids(text, master) == ["mall-of-arabia"]


def test_riyadh_only_rejects_riyadh_mall_b() -> None:
    master = load_master_data()
    accepted, rejected = filter_mall_ids(
        ["riyadh-mall-b"],
        [],
        "We want a store in Riyadh",
        master,
    )
    assert accepted == []
    assert rejected == ["riyadh-mall-b"]
