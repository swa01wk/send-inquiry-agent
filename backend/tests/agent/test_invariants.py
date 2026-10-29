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
