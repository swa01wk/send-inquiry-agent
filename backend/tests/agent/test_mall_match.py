from app.agent.mall_match import (
    extract_mall_phrases,
    phrase_matches_seed_mall,
    unmatched_mall_phrases,
)
from app.domain.master import load_master_data


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
