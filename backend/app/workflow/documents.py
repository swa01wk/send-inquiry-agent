"""Per-document decisions on a case (demo feedback §3.4).

A case holds one `DocumentDecision` per intake document. Each decision names the upload
(`file_id`) it was made on; when the case's document is replaced, the decision for that type
starts again as pending (ADR-R4). Pure helpers, called by the state machine and the brief.
"""

from __future__ import annotations

from datetime import date

from app.domain.models import NON_INTAKE_DOC_TYPES, DocType
from app.policy.config import get_policy
from app.workflow.expiry import expiry_status, expiry_tracked
from app.workflow.models import Case, DocumentDecision


def current_decisions(case: Case) -> dict[DocType, DocumentDecision]:
    """The decision for each intake document now on the case: the stored one if it's about
    the current upload, otherwise a new pending one from that upload's review result."""
    decisions: dict[DocType, DocumentDecision] = {}
    for doc_type, ref in case.draft.documents.items():
        if doc_type in NON_INTAKE_DOC_TYPES:
            continue
        stored = case.document_decisions.get(doc_type)
        if stored is not None and stored.file_id == ref.file_id:
            decisions[doc_type] = stored
        else:
            decisions[doc_type] = DocumentDecision.for_upload(ref)
    return decisions


def document_blockers(case: Case, today: date) -> list[str]:
    """What stops first-level approval (`approved_first`), in document order:
    `document_pending:<type>` for a required document not yet approved,
    `document_rejected:<type>` for any rejected document, and `expiry_unconfirmed:<type>` for
    a document whose type carries an expiry and whose date isn't known."""
    policy = get_policy()
    if not policy.document_approval:
        return []
    blockers: list[str] = []
    decisions = current_decisions(case)
    for doc_type in DocType:
        decision = decisions.get(doc_type)
        if decision is None:
            continue
        if decision.status == "rejected":
            blockers.append(f"document_rejected:{doc_type.value}")
        elif decision.status == "pending" and policy.documents.is_required(doc_type.value):
            blockers.append(f"document_pending:{doc_type.value}")
        if (
            decision.status != "rejected"
            and expiry_tracked(doc_type.value, policy)
            and expiry_status(decision, today, policy) == "unknown"
        ):
            blockers.append(f"expiry_unconfirmed:{doc_type.value}")
    return blockers
