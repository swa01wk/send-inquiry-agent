"""The case brief (L4 §3.6): deterministic, built only from the case and its audit trail.

Every line traces to a field (with its source and evidence), a document record, a
request, a decision or an audit event. No model call. The reviewer console shows it, and
the reviewer assistant (Day 5) answers from it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.fields import FIELD_BY_KEY, FieldGroup, document_definitions, document_label
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey
from app.domain.rules import contact_verified
from app.workflow.machine import approval_blockers
from app.workflow.models import CONTACT_ROLE_LABELS, ROLE_LABELS, Case, CaseStatus


class BriefField(BaseModel):
    key: str
    label: str
    group: str
    display: str | None
    source: str | None
    confirmed: bool
    evidence: str | None = None


class BriefDocument(BaseModel):
    doc_type: str
    label: str
    required: bool
    uploaded: bool
    file_id: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None
    uploaded_at: datetime | None = None
    replaced_versions: int = 0


class BriefRequest(BaseModel):
    id: str
    kind: str
    status: str
    remarks: str
    doc_types: list[str]
    requested_by: str
    requested_at: datetime
    closed_at: datetime | None


class BriefDecision(BaseModel):
    level: str
    outcome: str
    remarks: str | None
    reason_category: str | None
    by: str
    at: datetime


class BriefContact(BaseModel):
    role: str
    label: str
    name: str | None
    email: str | None
    phone: str | None
    same_as_primary: bool


class StageAge(BaseModel):
    stage: str
    entered_at: datetime
    days: float


class CaseBrief(BaseModel):
    reference: str
    status: str
    stage_label: str
    waiting_on: Literal["reviewer", "applicant", "system", "nobody"]
    queue_role: str | None
    queue_region: str | None
    channel: str
    company: str | None
    brand: str | None
    product_line: str | None
    mall: str | None
    region: str | None
    cr_status: str
    submitted_at: datetime
    fields: list[BriefField]
    verification: dict[str, bool]
    documents: list[BriefDocument]
    sales_data: BriefDocument | None
    contacts: list[BriefContact]
    requests: list[BriefRequest]
    decisions: list[BriefDecision]
    follow_on_of: str | None
    yardi: dict[str, Any]
    stage_ages: list[StageAge]
    next_decision_checklist: list[str] = Field(default_factory=list)


STAGE_LABELS: dict[str, str] = {
    "submitted": "Submitted",
    "first_review": "First review",
    "reupload_requested": "First review — waiting for re-upload",
    "second_review": "Lead — second review",
    "approved": "Approved — sending to Yardi",
    "sent_to_yardi": "Approved and sent to Yardi",
    "rejected": "Not approved",
}


def waiting_on(case: Case) -> Literal["reviewer", "applicant", "system", "nobody"]:
    if case.status == CaseStatus.REUPLOAD_REQUESTED:
        return "applicant"
    if case.status == CaseStatus.SECOND_REVIEW and any(r.status == "open" for r in case.requests):
        return "applicant"
    if case.status in (CaseStatus.FIRST_REVIEW, CaseStatus.SECOND_REVIEW):
        return "reviewer"
    if case.status in (CaseStatus.SUBMITTED, CaseStatus.APPROVED):
        return "system"
    return "nobody"


def _checklist(case: Case) -> list[str]:
    items: list[str] = []
    if case.status == CaseStatus.REUPLOAD_REQUESTED:
        request = case.open_request("reupload")
        if request:
            labels = ", ".join(document_label(d) for d in request.doc_types)
            items.append(f"Waiting for the applicant to re-upload: {labels}.")
    if case.status == CaseStatus.FIRST_REVIEW:
        unconfirmed = [
            FIELD_BY_KEY[k].label
            for k, f in case.draft.fields.items()
            if f.value not in (None, "", []) and not f.confirmed
        ]
        if unconfirmed:
            items.append(f"Not confirmed by the applicant: {', '.join(unconfirmed)}.")
        if case.draft.cr_status == "skipped":
            items.append("CR was skipped: check the company details against the documents.")
        items.append("Check the profile and documents, then approve, reject or request re-upload.")
    if case.status == CaseStatus.SECOND_REVIEW:
        for blocker in approval_blockers(case):
            kind, _, detail = blocker.partition(":")
            if kind == "open_request":
                items.append(
                    f"Open request: {detail.replace('_', ' ')} (approve after it's answered)."
                )
            elif kind == "missing_contact":
                label = CONTACT_ROLE_LABELS.get(detail, detail)
                items.append(f"{label} missing: request contacts before final approval.")
        if not approval_blockers(case):
            items.append("Everything needed for final approval is in.")
    if case.status == CaseStatus.APPROVED and case.yardi.needs_operations:
        items.append("Yardi didn't acknowledge the lead: operations need to follow up.")
    return items


def _stage_ages(case: Case, now: datetime) -> list[StageAge]:
    entries: list[tuple[str, datetime]] = [("submitted", case.submitted_at)]
    for event in case.events:
        if event.to_status != event.from_status:
            entries.append((event.to_status.value, event.at))
    ages: list[StageAge] = []
    for index, (stage, entered) in enumerate(entries):
        left = entries[index + 1][1] if index + 1 < len(entries) else now
        ages.append(
            StageAge(
                stage=stage,
                entered_at=entered,
                days=round((left - entered).total_seconds() / 86400, 2),
            )
        )
    return ages


def build_case_brief(case: Case, master: MasterData, *, now: datetime | None = None) -> CaseBrief:
    draft = case.draft
    now = now or datetime.now(tz=UTC)
    fields: list[BriefField] = []
    for d in FIELD_BY_KEY.values():
        value = draft.fields[d.key]
        if d.group == FieldGroup.DOCUMENTS and value.value is None:
            continue
        fields.append(
            BriefField(
                key=d.key.value,
                label=d.label,
                group=d.group.value,
                display=d.display(draft, master),
                source=value.source.value if value.source is not None else None,
                confirmed=value.confirmed,
                evidence=value.evidence,
            )
        )
    history_counts: dict[DocType, int] = {}
    for old_ref in case.document_history:
        history_counts[old_ref.doc_type] = history_counts.get(old_ref.doc_type, 0) + 1
    documents = []
    for doc_type, label, required in document_definitions():
        ref = draft.documents.get(doc_type)
        documents.append(
            BriefDocument(
                doc_type=doc_type.value,
                label=label,
                required=required,
                uploaded=ref is not None,
                file_id=ref.file_id if ref else None,
                file_name=ref.file_name if ref else None,
                size_bytes=ref.size_bytes if ref else None,
                uploaded_at=ref.uploaded_at if ref else None,
                replaced_versions=history_counts.get(doc_type, 0),
            )
        )
    sales = case.sales_data
    sales_doc = (
        BriefDocument(
            doc_type=DocType.SALES_DATA.value,
            label="Estimated sales data",
            required=False,
            uploaded=True,
            file_id=sales.file_id,
            file_name=sales.file_name,
            size_bytes=sales.size_bytes,
            uploaded_at=sales.uploaded_at,
            replaced_versions=history_counts.get(DocType.SALES_DATA, 0),
        )
        if sales
        else None
    )
    malls = draft.fields[FieldKey.MALLS].value or []
    mall_id = malls[0] if malls else None
    queue = case.review_queue

    def phone(c: Any) -> str | None:
        number = c.mobile.value or c.landline.value
        return str(number) if number else None

    return CaseBrief(
        reference=case.reference,
        status=case.status.value,
        stage_label=STAGE_LABELS.get(case.status.value, case.status.value),
        waiting_on=waiting_on(case),
        queue_role=ROLE_LABELS.get(queue.role) if queue else None,
        queue_region=queue.region if queue else None,
        channel="self_service",
        company=draft.fields[FieldKey.COMPANY_NAME].value,
        brand=draft.fields[FieldKey.BRAND_NAME_EN].value,
        product_line=draft.fields[FieldKey.UNIT_TYPE].value,
        mall=master.label_for("malls", mall_id) if mall_id else None,
        region=queue.region if queue else None,
        cr_status=draft.cr_status,
        submitted_at=case.submitted_at,
        fields=fields,
        verification={
            "email_verified": draft.email_verified,
            "mobile_verified": draft.mobile_verified,
            "contact_verified": contact_verified(draft),
        },
        documents=documents,
        sales_data=sales_doc,
        contacts=[
            BriefContact(
                role=c.role,
                label=CONTACT_ROLE_LABELS.get(c.role, c.role),
                name=" ".join(str(p) for p in (c.first_name.value, c.last_name.value) if p) or None,
                email=c.email.value,
                phone=phone(c),
                same_as_primary=c.same_as_primary,
            )
            for c in case.tenant_contacts
        ],
        requests=[
            BriefRequest(
                id=r.id,
                kind=r.kind,
                status=r.status,
                remarks=r.remarks,
                doc_types=[d.value for d in r.doc_types],
                requested_by=r.requested_by,
                requested_at=r.requested_at,
                closed_at=r.closed_at,
            )
            for r in case.requests
        ],
        decisions=[BriefDecision(**d.model_dump()) for d in case.decisions],
        follow_on_of=draft.follow_on_of,
        yardi=case.yardi.model_dump(mode="json"),
        stage_ages=_stage_ages(case, now),
        next_decision_checklist=_checklist(case),
    )
