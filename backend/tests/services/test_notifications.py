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
    "case_id": "CC-123456",
    "short_ref": "INQ-ABC123",
    "reason_label": "The applicant asked to speak to someone",
    "summary": "Stage: verifying.",
    "contact_name": "Sara Ali",
    "reviewer_name": "Faisal Al Qahtani",
    "console_url": "http://localhost:5173/review/cases/GEO-STR-123456",
    "case_url": "http://localhost:5173/inquiry/case?t=c",
    "documents": "- Brand Profile",
    "remarks": "The brand profile is from 2019.",
    "after_rejection": "You can raise a new inquiry at any time.",
    "role_label": "Company Admin",
    "accept_url": "http://localhost:8000/api/dev/identity/accept/inv_1",
    "request_label": "sales data",
    "hours": 49,
    "threshold_hours": 48,
    "stage_label": "First review",
    "queue_label": "Regional Leasing Manager (Store), Central",
    "message": "We're still waiting for your company contacts.",
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
