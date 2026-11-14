"""Three demo cases for the 10 Nov re-demo (day R5, demo feedback §5).

`POST /api/dev/reset` wipes everything and calls `seed_demo`; `make demo` seeds on start when
the store holds no case (`DEMO_SEED`). The cases go through the same code as a real one, so
the console, the outbox, the audit timeline and the applicant's links behave as usual:

- the inquiry is submitted with the `accept_and_submit` action handler (reference, notices,
  case created and routed);
- documents are stored and reviewed by the document review service (mock: expiry from the
  file name, fields from `mock_world/document_review.json`);
- reviewer decisions are applied with `apply_event` as the reviewer from the case's queue;
- the applicant's contacts go through the `signatory_answer` and `submit_contacts` handlers.

No model is called: only action handlers run, never an agent turn.

- **Case A** (first review): an expired Company Profile whose company name differs from the
  typed one, and a Brand Profile expiring soon.
- **Case B** (second review): documents approved; signatory "Yes, I'm the authorised
  signatory"; the billing contact waiting for the Lease Admin.
- **Case C** (sent to Yardi): everything approved.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Literal

from app.agent.actions import handle_ui_action
from app.agent.runtime import AgentRuntime
from app.domain import draft_ops
from app.domain.master import MasterData
from app.domain.models import DocType, FieldKey, InquiryDraft, Source
from app.policy.config import get_policy
from app.sessions import Session, SessionStore
from app.workflow.contacts import write_contacts
from app.workflow.machine import IllegalTransition
from app.workflow.models import Case, TenantContact, WorkflowEvent
from app.workflow.service import apply_event

logger = logging.getLogger(__name__)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
Level = Literal["first", "final"]


@dataclass(frozen=True)
class DemoCase:
    """One seeded case, as `/dev` lists it."""

    key: str  # "A" | "B" | "C"
    title: str
    reference: str
    status: str
    first_reviewer: str | None
    final_reviewer: str | None


@dataclass(frozen=True)
class _Persona:
    company: str
    address: str
    brand_en: str
    brand_ar: str
    first_name: str
    last_name: str
    email: str
    mobile: str
    unit_type: str
    category: str
    mall: str


# Their own names, emails and numbers: nothing collides with the live demo's applicant
# (Sara Ali, Bean Street) or the existing-tenant persona (Layla Hassan, Oasis Coffee), so
# the rehearsal's outbox lookups never pick up a seeded message.
_PERSONAS: dict[str, _Persona] = {
    "A": _Persona(
        "Qahwa House Trading Co.",
        "Tahlia Street, Riyadh",
        "Qahwa House",
        "قهوة هاوس",
        "Noura",
        "Al Saud",
        "noura@qahwahouse.example",
        "+966501110001",
        "specialty",
        "fnb_cafe",
        "riyadh-mall-a",
    ),
    "B": _Persona(
        "Desert Bloom Trading LLC",
        "Prince Sultan Road, Riyadh",
        "Desert Bloom",
        "ديزرت بلوم",
        "Khalid",
        "Al Harbi",
        "khalid@desertbloom.example",
        "+966501110002",
        "store",
        "fashion",
        "riyadh-mall-a",
    ),
    "C": _Persona(
        "Najd Home Electronics Co.",
        "Olaya Street, Riyadh",
        "Najd Home",
        "نجد هوم",
        "Faisal",
        "Al Qahtani",
        "faisal@najdhome.example",
        "+966501110003",
        "store",
        "electronics",
        "riyadh-mall-a",
    ),
}

_TITLES = {
    "A": "First review: expired profile, profile mismatch",
    "B": "Lead Approved: contacts in, ready for the final Approve Lead",
    "C": "Approved and sent to Yardi",
}

# Case A's files: the mock reads expiry from the name ("expired", "soon") and the fields
# from mock_world/document_review.json (the company name there differs from the typed one).
_FILES: dict[str, dict[DocType, str]] = {
    "A": {
        DocType.COMPANY_PROFILE: "company_profile_seed_expired.pdf",
        DocType.BRAND_PROFILE: "brand_profile_soon.pdf",
    },
    "B": {
        DocType.COMPANY_PROFILE: "company_profile.pdf",
        DocType.BRAND_PROFILE: "brand_profile.pdf",
    },
    "C": {
        DocType.COMPANY_PROFILE: "company_profile.pdf",
        DocType.BRAND_PROFILE: "brand_profile.pdf",
    },
}


def _draft(persona: _Persona, master: MasterData) -> InquiryDraft:
    """A complete, verified draft, as the applicant leaves it before Submit."""
    entries: list[draft_ops.WriteEntry] = [
        (FieldKey.COMPANY_NAME.value, persona.company, Source.USER),
        (FieldKey.COMPANY_ADDRESS.value, persona.address, Source.USER),
        (FieldKey.BRAND_NAME_EN.value, persona.brand_en, Source.USER),
        (FieldKey.BRAND_NAME_AR.value, persona.brand_ar, Source.USER),
        (FieldKey.UNIT_TYPE.value, persona.unit_type, Source.USER),
        (FieldKey.SALES_CATEGORY.value, persona.category, Source.USER),
        (FieldKey.MALLS.value, [persona.mall], Source.USER),
        (FieldKey.FIRST_NAME.value, persona.first_name, Source.USER),
        (FieldKey.LAST_NAME.value, persona.last_name, Source.USER),
        (FieldKey.EMAIL.value, persona.email, Source.USER),
        (FieldKey.MOBILE.value, persona.mobile, Source.USER),
    ]
    draft, _written, errors = draft_ops.write_fields(
        draft_ops.new_inquiry_draft(), entries, master=master
    )
    if errors:
        raise ValueError(f"demo seed draft: {errors}")
    draft.cr_status = "skipped"
    draft.email_verified = True
    draft.mobile_verified = True
    draft.email_link_sent_to = persona.email
    draft.otp_sent_to = persona.mobile
    return draft


def _attach_documents(
    runtime: AgentRuntime, session_id: str, draft: InquiryDraft, files: dict[DocType, str]
) -> InquiryDraft:
    """Store each file and review it, as the upload API does (no fill: the values are typed)."""
    services = runtime.services
    for doc_type, file_name in files.items():
        ref = services.storage.save(session_id, doc_type, file_name, iter([PDF]), len(PDF))
        review = services.document_review.review(ref, PDF)
        draft.documents[doc_type] = ref.model_copy(update={"review": review})
    return draft


def reviewer_for(runtime: AgentRuntime, case: Case, level: Level) -> str | None:
    """The first reviewer in the case's queue for `level` (dev seed endpoints)."""
    return _reviewer(runtime, case, level)


def _reviewer(runtime: AgentRuntime, case: Case, level: Level) -> str | None:
    queue = case.review_queue
    if queue is None:
        return None
    reviewers = runtime.services.reviewers.for_queue(queue.role_for(level), queue.region)
    return reviewers[0].id if reviewers else None


async def _act(
    runtime: AgentRuntime, case: Case, level: Level, name: str, payload: dict[str, Any]
) -> Case:
    reviewer_id = _reviewer(runtime, case, level)
    reviewer = runtime.services.reviewers.get(reviewer_id or "")
    if reviewer is None:
        raise RuntimeError(f"demo seed: no {level} reviewer for {case.reference}")
    return await apply_event(
        runtime, case.id, WorkflowEvent(name=name, payload=payload), reviewer.actor()
    )


async def _submit(runtime: AgentRuntime, store: SessionStore, key: str) -> tuple[Session, Case]:
    persona = _PERSONAS[key]
    session = await store.create()
    draft = _draft(persona, runtime.master)
    session.draft = _attach_documents(runtime, session.id, draft, _FILES[key])
    result = await handle_ui_action("accept_and_submit", {"terms_accepted": True}, session, runtime)
    await store.save(session)
    reference = session.draft.reference
    case = runtime.services.cases.get(reference or "")
    if case is None:
        raise RuntimeError(f"demo seed {key}: submit failed ({result.note.content})")
    return session, case


async def _approve_documents(runtime: AgentRuntime, case: Case) -> Case:
    for doc_type, ref in case.draft.documents.items():
        case = await _act(
            runtime,
            case,
            "first",
            "document_approved",
            {"doc_type": doc_type.value, "file_id": ref.file_id},
        )
    return case


async def _send_contacts(runtime: AgentRuntime, store: SessionStore, case: Case) -> Case:
    """The applicant opens the contacts request, answers "Yes, I'm the authorised signatory"
    and sends a billing contact."""
    if case.open_request("contacts") is None:
        case = await _act(
            runtime,
            case,
            "final",
            "contacts_requested",
            {"remarks": "Please add your billing contact."},
        )
    session = await store.create(draft=case.draft, mode="case", case_id=case.id)
    await handle_ui_action("signatory_answer", {"is_signatory": True}, session, runtime)
    company = case.draft.fields[FieldKey.COMPANY_NAME].value
    persona = next(p for p in _PERSONAS.values() if p.company == company)
    current = [TenantContact.model_validate(c) for c in session.contacts_draft]
    contacts, errors = write_contacts(
        current,
        [
            {
                "role": "billing_contact",
                "first_name": "Omar",
                "last_name": "Saleh",
                "email": f"billing@{persona.email.split('@', 1)[1]}",
                "contact_number": "+966551234567",
            }
        ],
        session.draft,
    )
    if errors:
        raise ValueError(f"demo seed contacts: {errors}")
    session.contacts_draft = [c.model_dump(mode="json") for c in contacts]
    await handle_ui_action("submit_contacts", {}, session, runtime)
    await store.save(session)
    updated = runtime.services.cases.get(case.id)
    if updated is None:
        raise RuntimeError("demo seed: case disappeared")
    return updated


async def _approve_contacts(runtime: AgentRuntime, case: Case) -> Case:
    for contact in list(case.tenant_contacts):
        if contact.approval != "pending":
            continue
        case = await _act(
            runtime, case, "first", "contact_approved", {"contact_id": contact.contact_id}
        )
    return case


async def _lead_approve(runtime: AgentRuntime, case: Case) -> Case:
    """Flow v2 (§3.7): the final reviewer assigns the unit, then "Approve Lead?" = Yes."""
    malls = case.draft.fields[FieldKey.MALLS].value
    mall = str(malls[0]) if isinstance(malls, list) and malls else ""
    case = await _act(
        runtime,
        case,
        "final",
        "unit_assigned",
        {"mall_id": mall, "unit_ref": "G-014", "area_sqm": 45},
    )
    return await _act(runtime, case, "final", "lead_approved", {})


FlowSeedStage = Literal["submitted", "qualified", "lead_approved"]


async def seed_flow_case(
    runtime: AgentRuntime,
    store: SessionStore,
    stage: FlowSeedStage,
    *,
    unit_type: str | None = None,
    malls: list[str] | None = None,
    cr_number: str | None = None,
) -> tuple[Case, str]:
    """A case at `stage`, built by applying the real events in order (flow v2 §3.1), so its
    chart path is the real one. For the after-submit Playwright scenarios (S18–S24).
    Returns the case and the applicant's email."""
    persona = _PERSONAS["B"]
    if unit_type or malls:
        persona = replace(
            persona,
            unit_type=unit_type or persona.unit_type,
            mall=(malls or [persona.mall])[0],
        )
    session = await store.create()
    draft = _draft(persona, runtime.master)
    if malls and len(malls) > 1:
        draft, _written, errors = draft_ops.write_fields(
            draft, [(FieldKey.MALLS.value, malls, Source.USER)], master=runtime.master
        )
        if errors:
            raise ValueError(f"flow seed malls: {errors}")
    if cr_number:
        draft, _written, errors = draft_ops.write_fields(
            draft, [(FieldKey.CR_NUMBER.value, cr_number, Source.USER)], master=runtime.master
        )
        if errors:
            raise ValueError(f"flow seed CR: {errors}")
        draft.cr_status = "new"
    session.draft = _attach_documents(runtime, session.id, draft, _FILES["B"])
    result = await handle_ui_action("accept_and_submit", {"terms_accepted": True}, session, runtime)
    await store.save(session)
    case = runtime.services.cases.get(session.draft.reference or "")
    if case is None:
        raise RuntimeError(f"flow seed: submit failed ({result.note.content})")
    if stage in ("qualified", "lead_approved"):
        case = await _approve_documents(runtime, case)
        case = await _act(runtime, case, "first", "approved_first", {})
    if stage == "lead_approved":
        case = await _lead_approve(runtime, case)
    return case, persona.email


async def seed_demo(runtime: AgentRuntime, store: SessionStore) -> list[DemoCase]:
    """Seed cases A, B and C. A case that fails to seed is logged and skipped."""
    seeded: list[DemoCase] = []
    for key in ("A", "B", "C"):
        try:
            _session, case = await _submit(runtime, store, key)
            if key in ("B", "C"):
                case = await _approve_documents(runtime, case)
                case = await _act(runtime, case, "first", "approved_first", {})
                if get_policy().lead_approval.enabled:
                    case = await _lead_approve(runtime, case)
                case = await _send_contacts(runtime, store, case)
            if key == "C":
                if get_policy().contacts.approval_required:
                    case = await _approve_contacts(runtime, case)
                case = await _act(runtime, case, "final", "approved", {})
        except (IllegalTransition, RuntimeError, ValueError):
            logger.exception("demo seed: case %s failed", key)
            continue
        seeded.append(
            DemoCase(
                key=key,
                title=_TITLES[key],
                reference=case.reference,
                status=case.status.value,
                first_reviewer=_reviewer(runtime, case, "first"),
                final_reviewer=_reviewer(runtime, case, "final"),
            )
        )
    return seeded


def list_demo_cases(runtime: AgentRuntime) -> list[DemoCase]:
    """The seeded cases still in the store (by the personas' company names)."""
    by_company = {p.company: k for k, p in _PERSONAS.items()}
    out: list[DemoCase] = []
    for case in runtime.services.cases.all():
        key = by_company.get(str(case.draft.fields[FieldKey.COMPANY_NAME].value or ""))
        if key is None or any(d.key == key for d in out):
            continue
        out.append(
            DemoCase(
                key=key,
                title=_TITLES[key],
                reference=case.reference,
                status=case.status.value,
                first_reviewer=_reviewer(runtime, case, "first"),
                final_reviewer=_reviewer(runtime, case, "final"),
            )
        )
    return sorted(out, key=lambda d: d.key)


__all__ = ["DemoCase", "list_demo_cases", "seed_demo"]
