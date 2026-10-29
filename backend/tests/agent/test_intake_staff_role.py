from app.agent.channels import intake_staff_role
from app.services.reviewers import ReviewerDirectory


def test_intake_staff_role_for_guest_service() -> None:
    reviewers = ReviewerDirectory()
    role = intake_staff_role(reviewers, "assisted", "guest-service-1")
    assert role == "guest_service"


def test_intake_staff_role_absent_for_self_service() -> None:
    reviewers = ReviewerDirectory()
    assert intake_staff_role(reviewers, "self_service", "guest-service-1") is None
    assert intake_staff_role(reviewers, "assisted", None) is None
