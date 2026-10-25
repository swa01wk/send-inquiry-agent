import pytest
from app.agent.guard import _FALSE_SUBMIT_RE, claims_submission, message_likely_has_inquiry_data


@pytest.mark.parametrize(
    "text",
    [
        "Your inquiry has been submitted! Here is your reference.",
        "Great news, your enquiry was sent to the leasing team.",
        "I've submitted your inquiry.",
        "Your reference number is GEO-STR-123456.",
    ],
)
def test_false_submit_claims_match(text: str) -> None:
    assert _FALSE_SUBMIT_RE.search(text)
    assert claims_submission(text)


@pytest.mark.parametrize(
    "text",
    [
        # Live test 14: the guard retracted these, so the reply flickered.
        "Our leasing team contacts every applicant once the inquiry is sent, so we can keep going.",
        "Our leasing team will contact applicants after the inquiry is sent.",
        "When your application is received, the team reviews it.",
        "As soon as the request is submitted you'll get a reference.",
    ],
)
def test_conditional_mentions_are_not_claims(text: str) -> None:
    assert not claims_submission(text)


def test_claim_after_a_conditional_mention_still_counts() -> None:
    text = "Once the inquiry is sent we review it. Good news: your inquiry has been submitted."
    assert claims_submission(text)


@pytest.mark.parametrize(
    "text",
    [
        "For your reference, malls are listed below.",
        "Once you submit, our team reviews your inquiry.",
        "You can submit from the review card when you're ready.",
        "Reference GEO-STR-100001 is under review with our leasing team.",
    ],
)
def test_benign_text_does_not_match(text: str) -> None:
    assert not _FALSE_SUBMIT_RE.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "Bean Street, a coffee kiosk at Riyadh Mall A, about 30 sqm",
        "Sara Ali, sara@beanstreet.sa, 0501234567",
        "Acme Trading LLC on King Abdullah Road",
    ],
)
def test_data_messages_detected(text: str) -> None:
    assert message_likely_has_inquiry_data(text)


@pytest.mark.parametrize(
    "text",
    [
        "Which malls do you have in Riyadh?",
        "What documents do I need for a coffee kiosk",
        "Hey! Crazy weather today, isn't it?",
        "[ui_event] malls_selected: Riyadh Mall A",
        "thanks",
    ],
)
def test_questions_and_chat_not_treated_as_data(text: str) -> None:
    assert not message_likely_has_inquiry_data(text)


@pytest.mark.parametrize(
    "text",
    [
        "السلام عليكم",
        "شكرا",
        "كم تستغرق المراجعة؟",
    ],
)
def test_arabic_greeting_and_questions_not_treated_as_data(text: str) -> None:
    assert not message_likely_has_inquiry_data(text)


def test_cr_pattern_ignores_local_mobile_numbers() -> None:
    from app.agent.guard import _CR_NUMBER_RE

    assert _CR_NUMBER_RE.search("My CR is 1010123456")
    assert not _CR_NUMBER_RE.search("Call me on 0501234567")
