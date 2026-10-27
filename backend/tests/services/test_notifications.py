import pytest
from app.notifications import TEMPLATE_NAMES, MockNotificationService, load_template, render

CONTEXT = {
    "first_name": "Sara",
    "brand": "Bean Street",
    "mall": "Riyadh Mall A",
    "reference": "GEO-STR-123456",
    "tracking_url": "http://localhost:5173/inquiry/status/GEO-STR-123456?t=x",
    "verify_url": "http://localhost:5173/inquiry/verify?t=y",
    "resume_url": "http://localhost:5173/inquiry/resume?t=z",
    "code": "1234",
    "ttl_hours": 72,
    "ttl_days": 7,
}


@pytest.mark.parametrize("name", TEMPLATE_NAMES)
def test_every_template_renders_completely(name: str) -> None:
    template, subject, body = render(name, CONTEXT)
    assert "$" not in subject + body
    assert template.kind in ("information", "action_required")


def test_template_kinds_and_channels() -> None:
    assert load_template("email_verification_link").kind == "action_required"
    assert load_template("submission_email").kind == "information"
    assert load_template("sms_otp").channel == "sms"


@pytest.mark.asyncio
async def test_outbox_newest_first_filter_clear_and_restart(tmp_path) -> None:
    service = MockNotificationService(str(tmp_path))
    await service.send("submission_email", "sara@x.example", CONTEXT, inquiry_id="s1")
    await service.send("submission_sms", "+966501234567", CONTEXT, inquiry_id="s1")
    messages = service.messages()
    assert [m["template"] for m in messages] == ["submission_sms", "submission_email"]
    email = service.messages(to="sara@x.example")
    assert len(email) == 1
    assert email[0]["links"] == [CONTEXT["tracking_url"]]
    assert len(MockNotificationService(str(tmp_path)).messages()) == 2
    service.clear()
    assert service.messages() == []
