"""The verification card never carries the email link (18 Nov B1, N7, NG5, ADR-N3).

The applicant opens the link from their email; tests and demos from the dev outbox. There is
no demo mode: `EMAIL_LINK_DEMO` and `demo_token` are gone.
"""

from __future__ import annotations

from app.api.cards import build_verification_card
from app.api.schemas import VerificationEmail
from app.config import Settings
from app.domain.draft_ops import new_inquiry_draft
from app.domain.master import load_master_data
from tests.domain.conftest import fill_minimal_collectible


def test_the_card_payload_has_no_link_token() -> None:
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.email_link_sent_to = "sara@beanstreet.example"

    card = build_verification_card(draft)

    assert "demo_token" not in card.payload["email"]
    assert "demo_token" not in VerificationEmail.model_fields


def test_there_is_no_demo_link_setting(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_LINK_DEMO", "true")

    settings = Settings(token_secret="test-secret")

    assert not hasattr(settings, "email_link_demo")
