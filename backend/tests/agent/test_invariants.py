import pytest
from app.agent.invariants import SecretSet, TurnContext, check_turn
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source

pytestmark = pytest.mark.agent


def test_i1_submission_claim_without_ui_event_fails() -> None:
    ctx = TurnContext(
        assistant_text="Your inquiry has been submitted! Here is your reference.",
        ui_evidence="",
    )
    hits = check_turn(ctx)
    assert any(v.invariant == "I1" for v in hits)


def test_i1_conditional_mention_passes() -> None:
    ctx = TurnContext(
        assistant_text=(
            "Our leasing team contacts every applicant once the inquiry is sent, "
            "so we can keep going."
        ),
        ui_evidence="",
    )
    assert not any(v.invariant == "I1" for v in check_turn(ctx))


def test_i2_otp_in_reply_fails() -> None:
    ctx = TurnContext(
        assistant_text="Please enter 1234 to verify your mobile.",
        secrets=SecretSet(codes={"1234"}),
    )
    hits = check_turn(ctx)
    assert any(v.invariant == "I2" for v in hits)


def test_i2_otp_not_in_secrets_set_passes() -> None:
    ctx = TurnContext(
        assistant_text="Please enter 1234 to verify your mobile.",
        secrets=SecretSet(),
    )
    assert not any(v.invariant == "I2" for v in check_turn(ctx))


def test_i4_unconfirmed_derived_at_submit_fails() -> None:
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(),
        [(FieldKey.COMPANY_NAME.value, "Acme LLC", Source.DERIVED)],
        master=master,
    )
    draft.reference = "GEO-STR-100001"
    before = draft.model_copy(deep=True)
    before.reference = None
    ctx = TurnContext(
        assistant_text="Thank you!",
        draft_before=before,
        draft_after=draft,
        audit_events_new=[{"type": "submit_result", "payload": {"reference": "GEO-STR-100001"}}],
    )
    hits = check_turn(ctx)
    assert any(v.invariant == "I4" for v in hits)


def test_i7_sar_price_fails() -> None:
    ctx = TurnContext(assistant_text="Rent is about 50,000 SAR per year at that mall.")
    assert any(v.invariant == "I7" for v in check_turn(ctx))


# ---- False-positive guards (review of #50) -------------------------------------------


def test_i2_codes_come_only_from_sms_messages() -> None:
    from app.agent.invariants import secrets_from_outbox_messages

    secrets = secrets_from_outbox_messages(
        [
            {"template": "review_assigned", "body": "Queue for 2026, unit 1407", "links": []},
            {"template": "sms_otp", "body": "Your Cenomi code is 1234", "links": []},
            {
                "template": "email_verification_link",
                "body": "",
                "links": ["http://x/v?t=abcDEF123456"],
            },
        ]
    )
    assert secrets.codes == {"1234"}
    assert secrets.tokens == {"abcDEF123456"}


def test_i5_applicant_sharing_a_reviewer_name_passes() -> None:
    # T-1002's contact is Khalid; a reviewer is Khalid Bakr. Greeting the applicant is fine.
    ctx = TurnContext(
        assistant_text="Thanks, Khalid. Which brand is this inquiry for?",
        session_contact_hints={"khalid alnoor", "khalid", "alnoor"},
    )
    assert not any(v.invariant == "I5" for v in check_turn(ctx))


def test_i5_reviewer_name_still_fails() -> None:
    ctx = TurnContext(
        assistant_text="Khalid Bakr from the leasing team will look at it.",
        session_contact_hints={"sara ali", "sara", "ali"},
    )
    assert any(v.invariant == "I5" for v in check_turn(ctx))


@pytest.mark.parametrize(
    "text",
    [
        "A kiosk within your budget at Riyadh Mall A is a good fit.",
        "A 365 days lease is the default; you can change it.",
    ],
)
def test_i7_ordinary_within_and_days_pass(text: str) -> None:
    assert not any(v.invariant == "I7" for v in check_turn(TurnContext(assistant_text=text)))


@pytest.mark.parametrize(
    "text",
    [
        "You'll hear back within 3 days.",
        "The leasing team will reply within a few business days.",
        "Approval is guaranteed for this brand.",
    ],
)
def test_i7_time_promises_fail(text: str) -> None:
    assert any(v.invariant == "I7" for v in check_turn(TurnContext(assistant_text=text)))


def test_i7_reading_back_the_applicants_budget_passes() -> None:
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(),
        [(FieldKey.RENT_MAX.value, 250000, Source.USER)],
        master=master,
    )
    ctx = TurnContext(
        assistant_text="Noted: a budget of up to 250,000 SAR a year.",
        draft_after=draft,
    )
    assert not any(v.invariant == "I7" for v in check_turn(ctx))
