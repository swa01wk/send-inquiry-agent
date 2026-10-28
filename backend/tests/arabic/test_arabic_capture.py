"""Arabic business words trigger guard capture heuristics (L3 §3.10)."""

from app.agent.guard import message_likely_has_inquiry_data


def test_arabic_business_words_count_as_inquiry_data() -> None:
    assert message_likely_has_inquiry_data("نبي كشك قهوة في الرياض مول أ")
    assert message_likely_has_inquiry_data("متجر نظارات في جدة")
    assert message_likely_has_inquiry_data("مطعم عائلي ~80 متر")
    assert message_likely_has_inquiry_data("مقهى مختص في مول")
