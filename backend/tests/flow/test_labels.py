"""Chart names (flow v2 §3.5, FV2): what applicants and reviewers read follows the v2 chart."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.domain.models import new_inquiry_draft
from app.services.status import (
    OWNER_ROLES,
    STAGES,
    InquiryStatus,
    inquiry_status_summary,
    status_stages,
)
from app.workflow.labels import (
    LEAD_REJECTED,
    STAGE_LABELS,
    TENANT_NOT_QUALIFIED,
    rejection_label,
    role_label,
    status_label,
)
from app.workflow.models import Case, CaseStatus, Decision

REPO = Path(__file__).resolve().parents[3]
T0 = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)

# Wording the v2 chart replaced (V4, V5, V8). Ids such as `rlm_store` or `sales_data` stay.
RETIRED = (
    "Lead — second review",
    "Regional Leasing Manager",
    "Regional Property Leasing Manager",
    "estimated sales",
    "Lease Admin",
)

# What applicants and reviewers read: templates, prompts, label maps.
READ_BY_PEOPLE = [
    *sorted((REPO / "backend/app/notifications/templates").glob("*.txt")),
    REPO / "backend/app/agent/system_prompt.md",
    REPO / "backend/app/agent/system_prompt_v2.md",
    REPO / "backend/app/agent/case_prompt.md",
    REPO / "backend/app/agent/reviewer_prompt.md",
    REPO / "backend/app/workflow/labels.py",
    REPO / "backend/app/workflow/models.py",
    REPO / "backend/app/services/status.py",
    REPO / "frontend/src/review/reviewerSession.ts",
    REPO / "frontend/src/components/cards/SalesDataUploadCard.tsx",
]


def _case(status: CaseStatus, *levels: str) -> Case:
    case = Case(
        id="GEO-STR-123456",
        reference="GEO-STR-123456",
        session_id="s-1",
        status=status,
        draft=new_inquiry_draft(),
        submitted_at=T0,
    )
    for level in levels:
        case.decisions.append(
            Decision(level=level, outcome="rejected", remarks="x", by="r", at=T0)  # type: ignore[arg-type]
        )
    return case


def test_status_labels_follow_the_chart() -> None:
    assert STAGE_LABELS["first_review"] == "With the Leasing Admin"
    assert STAGE_LABELS["second_review"] == "Tenant Qualified"
    assert status_label(_case(CaseStatus.SECOND_REVIEW)) == "Tenant Qualified"
    assert status_label(_case(CaseStatus.REJECTED, "first")) == TENANT_NOT_QUALIFIED
    assert status_label(_case(CaseStatus.REJECTED, "second")) == LEAD_REJECTED
    assert rejection_label(_case(CaseStatus.FIRST_REVIEW)) is None


def test_role_labels_follow_the_chart() -> None:
    assert role_label("lease_admin") == "Leasing Admin"
    assert role_label("rlm_store") == "Regional Sales Manager"
    assert role_label("rplm_media") == "Regional Product Line Manager (Media)"
    assert role_label(None) is None
    assert OWNER_ROLES["store"] == OWNER_ROLES["office"] == "Regional Sales Manager"


def test_status_page_names_the_stages_and_the_rejection() -> None:
    assert [label for _key, label in STAGES] == [
        "Inquiry submitted",
        "With the Leasing Admin",
        "Tenant Qualified",
        "Outcome",
    ]
    rejected = InquiryStatus(
        reference="GEO-STR-000001",
        status="rejected",
        submitted_at=T0,
        current_stage="outcome",
        rejection_label=LEAD_REJECTED,
    )
    assert status_stages(rejected)[-1] == ("outcome", "Outcome — Lead Rejected", "done")
    assert LEAD_REJECTED in inquiry_status_summary(rejected)


@pytest.mark.parametrize("path", READ_BY_PEOPLE, ids=lambda p: p.name)
def test_no_retired_wording(path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{path} not in this checkout")
    text = path.read_text(encoding="utf-8")
    found = [phrase for phrase in RETIRED if phrase.lower() in text.lower()]
    assert not found, f"{path.relative_to(REPO)} still says {found}"
