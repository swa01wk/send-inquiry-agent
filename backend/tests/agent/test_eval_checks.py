from app.agent.eval_checks import off_topic_offers_continue


def test_off_topic_offers_continue_accepts_prompt_phrasing() -> None:
    assert off_topic_offers_continue("I'm here for leasing — happy to carry on whenever you like.")
    assert off_topic_offers_continue("I can help you send a leasing inquiry instead.")
    hotel = (
        "I'm here for leasing inquiries, so I can help with a brand opening instead of "
        "hotel bookings. If you're looking to lease space in Jeddah, tell me about your brand."
    )
    assert off_topic_offers_continue(hotel)
    assert not off_topic_offers_continue("I'm here for Cenomi leasing inquiries only.")
