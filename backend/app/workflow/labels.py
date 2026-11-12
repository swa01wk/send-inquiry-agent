"""Display names from Cenomi's v2 flowchart (flow v2 §3.5, V4, V5, V8).

The one place for what applicants and reviewers read: case status, review stage and
reviewer role. Ids never change (ADR-V3): `rlm_store` stays the queue id and shows as
"Regional Sales Manager"; `second_review` stays the status id and shows as "Tenant
Qualified". A rejection is named by the level it came from: "Tenant Not Qualified" at
the first level ("Approve Prospective Tenant?" = No), "Lead Rejected" at the final level
("Approve Lead?" = No).
"""

from __future__ import annotations

from app.workflow.models import ROLE_LABELS, Case, CaseStatus

TENANT_NOT_QUALIFIED = "Tenant Not Qualified"
LEAD_REJECTED = "Lead Rejected"
FORECASTED_SALES_DATA = "Forecasted Sales Data"

# Case status → label (reviewer console, tenant portal, reviewer assistant, case brief).
# `rejected` is refined by `status_label`.
STAGE_LABELS: dict[str, str] = {
    "submitted": "Submitted",
    "first_review": "With the Leasing Admin",
    "reupload_requested": "With the Leasing Admin — waiting for re-upload",
    "second_review": "Tenant Qualified",
    "approved": "Approved — sending to Yardi",
    "sent_to_yardi": "Approved and sent to Yardi",
    "rejected": "Not approved",
}

# Status-page stages (`StatusService`) → label.
STATUS_PAGE_STAGES: dict[str, str] = {
    "submitted": "Inquiry submitted",
    "first_review": "With the Leasing Admin",
    "second_review": "Tenant Qualified",
    "outcome": "Outcome",
}


def rejection_label(case: Case) -> str | None:
    """ "Tenant Not Qualified" or "Lead Rejected" for a rejected case, else None."""
    if case.status != CaseStatus.REJECTED:
        return None
    last = next((d for d in reversed(case.decisions) if d.outcome == "rejected"), None)
    if last is None:
        return None
    return TENANT_NOT_QUALIFIED if last.level == "first" else LEAD_REJECTED


def status_label(case: Case) -> str:
    """The chart's name for where the case is."""
    return rejection_label(case) or STAGE_LABELS.get(case.status.value, case.status.value)


def role_label(role: str | None) -> str | None:
    """A reviewer role's display name; None stays None."""
    if role is None:
        return None
    return ROLE_LABELS.get(role, role)
