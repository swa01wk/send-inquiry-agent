"""Document expiry status (demo feedback §3.4): pure, computed in code (ADR-R1).

The date in force is the reviewer's (`expiry_confirmed`), else the document review
service's (`expiry_extracted`). "Today" is the caller's: the app clock (`app/clock.py`),
so the simulated clock moves a document from valid to expiring soon to expired.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from app.policy.config import PolicyConfig, get_policy
from app.workflow.models import DocumentDecision

ExpiryStatus = Literal["expired", "expiring_soon", "valid", "unknown"]

EXPIRY_LABELS: dict[str, str] = {
    "expired": "Expired",
    "expiring_soon": "Expiring soon",
    "valid": "Valid",
    "unknown": "Expiry not known",
}


def expiry_tracked(doc_type: str, policy: PolicyConfig | None = None) -> bool:
    """Whether this document type carries an expiry date (policy `document_expiry`)."""
    return str(doc_type) in (policy or get_policy()).document_expiry.doc_types


def expiry_status(
    decision: DocumentDecision, today: date, policy: PolicyConfig | None = None
) -> ExpiryStatus:
    """`expired` before today; `expiring_soon` less than `expiring_soon_days` away;
    `valid` otherwise; `unknown` with no date."""
    expiry = decision.expiry
    if expiry is None:
        return "unknown"
    if expiry < today:
        return "expired"
    soon_days = (policy or get_policy()).document_expiry.expiring_soon_days
    if (expiry - today).days < soon_days:
        return "expiring_soon"
    return "valid"


def expired_remarks(expiry: date) -> str:
    """The remark the console preselects for an expired document (§3.4)."""
    return f"This document expired on {expiry.strftime('%d %b %Y')}. Please upload a current one."
