"""The v2 flowchart's steps in code (flow v2 §3.1, ADR-V2, FV1).

Each box on Cenomi's "Prospective Tenant Journey" chart has an id (the ids on the scenario
page and in `docs/flow-v2/scenarios.json`). Code records a `flow_step` audit entry each
time a case reaches one, so a test can check the route a case took, not only where it
ended. The model never records a step.

This module covers the review lifecycle (day F2). Intake steps (`start`, `chk_tp`, `emv`,
`succ1`, …) are recorded by the intake code (F3), the call-centre steps by
`api/callcentre.py` (F4).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from app.workflow.models import Case, CaseStatus, WorkflowEvent

if TYPE_CHECKING:
    from app.agent.runtime import AgentRuntime


class FlowNode(StrEnum):
    # Tenant platform (self-service)
    START = "start"
    RAISE_TP = "raise_tp"
    CHK_TP = "chk_tp"
    DB = "db"
    EXIST = "exist"
    DISPLAY = "display"
    REDIRECT = "redirect"
    EMV = "emv"
    SUCC1 = "succ1"
    COMPLETE1 = "complete1"
    REF1 = "ref1"
    # Call centre
    RAISE_CC = "raise_cc"
    CHK_CC = "chk_cc"
    CRX = "crx"
    PCX = "pcx"
    INFORM = "inform"
    EXEC = "exec"
    EMAIL_LINK = "email_link"
    OPEN_FORM = "open_form"
    BIC = "bic"
    UPDATE_BI = "update_bi"
    MOB = "mob"
    SUCC2 = "succ2"
    UPLOAD_SUBMIT = "upload_submit"
    REF2 = "ref2"
    # First level
    VLA = "vla"
    DOCSOK = "docsok"
    REUP_REQ = "reup_req"
    REUP_MAIL = "reup_mail"
    REUP_SUBMIT = "reup_submit"
    APPROVE_PT = "approve_pt"
    NOT_Q = "not_q"
    REJ_MAIL = "rej_mail"
    PTC_CREATE = "ptc_create"
    AZ1 = "az1"
    REG_LINK1 = "reg_link1"
    QUALIFIED = "qualified"
    # Second level
    PROD2 = "prod2"
    RSM = "rsm"
    RPLM = "rplm"
    FSD_Q = "fsd_q"
    FSD_NOTIFY = "fsd_notify"
    FSD_PROVIDE = "fsd_provide"
    APPROVE_LEAD = "approve_lead"
    REQ_CONTACTS = "req_contacts"
    CONTACTS_NOTIFY = "contacts_notify"
    CONTACTS_PROVIDE = "contacts_provide"
    APPROVE_LEAD2 = "approve_lead2"
    REJECT_LEAD = "reject_lead"
    AZ2 = "az2"
    CREATE_ALL = "create_all"
    AZ3 = "az3"
    REG_LINK2 = "reg_link2"
    YARDI_BOX = "yardi_box"
    END = "end"


# Connectors and boxes outside the POC: never recorded; the path check skips them.
IGNORED_NODES: frozenset[str] = frozenset({"A1", "A2", "A3", "B1", "B2", "reg1", "reg2"})

# Product lines that take the "Product = Specialty/Media?" Yes branch (RPLM).
_PRODUCT_LINE_YES = frozenset({"media", "specialty"})


def record_flow_step(
    runtime: AgentRuntime,
    *,
    inquiry_id: str,
    node: FlowNode,
    actor: Literal["user", "agent", "system", "reviewer", "staff"] = "system",
    outcome: str | None = None,
) -> None:
    """One `flow_step` audit entry. `outcome` is the branch taken at a decision box."""
    record_flow_step_audit(
        runtime.services.audit, inquiry_id=inquiry_id, node=node, actor=actor, outcome=outcome
    )


def call_centre_flow_id(session: Any) -> str | None:
    """The staff chat id when this applicant chat continues a call-centre inquiry (§3.4):
    the applicant's steps are recorded there, so the chart path reads as one inquiry."""
    origin = getattr(session, "origin_id", None)
    return str(origin) if origin else None


def record_flow_step_audit(
    audit: Any,
    *,
    inquiry_id: str,
    node: FlowNode,
    actor: Literal["user", "agent", "system", "reviewer", "staff"] = "system",
    outcome: str | None = None,
) -> None:
    """`record_flow_step` where only the audit trail is at hand (session creation)."""
    payload: dict[str, Any] = {"node": node.value}
    if outcome is not None:
        payload["outcome"] = outcome
    audit.record(inquiry_id, "flow_step", actor=actor, payload=payload)


def flow_path(runtime: AgentRuntime, inquiry_id: str) -> list[dict[str, Any]]:
    """The recorded steps of one inquiry or case, oldest first."""
    return [
        {
            "seq": e.get("seq"),
            "at": e.get("at"),
            "node": (e.get("payload") or {}).get("node"),
            "outcome": (e.get("payload") or {}).get("outcome"),
            "actor": e.get("actor"),
        }
        for e in runtime.services.audit.events(inquiry_id)
        if e.get("type") == "flow_step"
    ]


def _asked_for_sales_data(case: Case) -> bool:
    return any(r.kind == "sales_data" for r in case.requests)


def transition_steps(
    before: Case, after: Case, event: WorkflowEvent
) -> list[tuple[FlowNode, str | None]]:
    """The chart steps a lifecycle event reaches, in chart order (spec §3.1 table).

    Steps that depend on an effect actually happening (an Azure AD invitation sent or
    revoked) are recorded by that effect instead.
    """
    name = event.name
    N = FlowNode
    if name == "submit_requested":
        return [(N.COMPLETE1, None)]
    if name == "submit_succeeded":
        return [(N.REF1, None)]
    if name == "routed":
        return [(N.VLA, None)]
    if name == "reupload_requested":
        return [(N.DOCSOK, "no"), (N.REUP_REQ, None), (N.REUP_MAIL, None)]
    if name == "documents_resubmitted":
        return [(N.REUP_SUBMIT, None)]
    if name == "approved_first":
        product = after.review_queue.product_line if after.review_queue else None
        return [
            (N.DOCSOK, "yes"),
            (N.APPROVE_PT, "yes"),
            (N.PTC_CREATE, None),
            (N.QUALIFIED, None),
            (N.PROD2, "yes" if product in _PRODUCT_LINE_YES else "no"),
        ]
    if name == "rejected":
        if before.status in (CaseStatus.FIRST_REVIEW, CaseStatus.REUPLOAD_REQUESTED):
            return [(N.APPROVE_PT, "no"), (N.NOT_Q, None), (N.REJ_MAIL, None)]
        steps: list[tuple[FlowNode, str | None]] = []
        if not _asked_for_sales_data(before):
            steps.append((N.FSD_Q, "no"))
        steps += [(N.APPROVE_LEAD, "no"), (N.REJECT_LEAD, None), (N.REJ_MAIL, None)]
        return steps
    if name == "unit_assigned":
        product = after.review_queue.product_line if after.review_queue else None
        return [(N.RPLM if product in _PRODUCT_LINE_YES else N.RSM, None)]
    if name == "sales_data_requested":
        return [(N.FSD_Q, "yes"), (N.FSD_NOTIFY, None)]
    if name == "sales_data_provided":
        return [(N.FSD_PROVIDE, None)]
    if name == "lead_approved":
        lead: list[tuple[FlowNode, str | None]] = []
        if not _asked_for_sales_data(before):
            lead.append((N.FSD_Q, "no"))
        lead.append((N.APPROVE_LEAD, "yes"))
        return lead
    if name == "contacts_requested" and before.status == CaseStatus.LEAD_APPROVED:
        return [(N.REQ_CONTACTS, None), (N.CONTACTS_NOTIFY, None)]
    if name == "contacts_provided" and before.status == CaseStatus.LEAD_APPROVED:
        return [(N.CONTACTS_PROVIDE, None)]
    if name == "approved" and before.status == CaseStatus.LEAD_APPROVED:
        return [(N.APPROVE_LEAD2, None), (N.CREATE_ALL, None)]
    if name == "sent_to_yardi":
        return [(N.YARDI_BOX, None), (N.END, None)]
    return []


def record_transition_steps(
    runtime: AgentRuntime,
    before: Case,
    after: Case,
    event: WorkflowEvent,
    actor: Literal["user", "agent", "system", "reviewer", "staff"],
) -> None:
    for node, outcome in transition_steps(before, after, event):
        record_flow_step(runtime, inquiry_id=after.id, node=node, actor=actor, outcome=outcome)
