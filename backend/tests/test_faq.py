from app.domain.faq import search_faq


def test_faq_search_review_time():
    results = search_faq("how long does approval take", k=2)
    assert len(results) >= 1
    assert results[0].id == "review_time"
