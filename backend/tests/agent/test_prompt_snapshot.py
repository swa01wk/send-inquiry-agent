"""Snapshot the assembled intake system prompt (AGENT-DET, testing strategy §2.4)."""

from __future__ import annotations

import difflib
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.agent.graph import system_for_turn
from app.agent.prompts import clear_prompt_cache
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import add_document, new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey, InquiryDraft, Source
from app.domain.rules import compute_phase
from app.domain.tenant_prefill import prefill_from_tenant
from langchain_core.runnables.config import RunnableConfig
from tests.domain.conftest import fill_minimal_collectible

_SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
_MAX_DIFF_LINES = 80


def _render(state: dict, runtime: AgentRuntime) -> str:
    config = RunnableConfig(
        configurable={"thread_id": state["session_id"], "runtime": runtime},
    )
    message = system_for_turn(state, config)
    content = message.content if isinstance(message.content, str) else str(message.content)
    return content if content.endswith("\n") else content + "\n"


def _state_for(
    draft: InquiryDraft,
    *,
    assisted: bool = False,
    channel: str | None = None,
    tenant_id: str | None = None,
    session_id: str = "prompt-snapshot",
) -> dict:
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id=session_id, draft=draft, phase=phase)
    state["cards_shown"] = []
    state["assisted"] = assisted
    if channel:
        state["channel"] = channel
    if tenant_id:
        state["tenant_id"] = tenant_id
    return state


def _ready_to_submit() -> InquiryDraft:
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    draft.email_verified = True
    draft.mobile_verified = True
    max_bytes = 5 * 1024 * 1024
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    for doc_type, file_id, name in (
        (DocType.COMPANY_PROFILE, "co-1", "company.pdf"),
        (DocType.BRAND_PROFILE, "br-1", "brand.pdf"),
    ):
        draft, _ = add_document(
            draft,
            doc_type,
            file_id=file_id,
            file_name=name,
            size_bytes=100,
            max_bytes=max_bytes,
            uploaded_at=ts,
        )
    return draft


def _assisted_collecting_draft() -> InquiryDraft:
    master = load_master_data()
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    entries = [
        (FieldKey.COMPANY_NAME.value, "Bean Street Trading Co.", Source.STAFF),
        (FieldKey.COMPANY_ADDRESS.value, "Olaya Street, Riyadh", Source.STAFF),
        (FieldKey.BRAND_NAME_EN.value, "Bean Street", Source.STAFF),
        (FieldKey.BRAND_NAME_AR.value, "بين ستريت", Source.STAFF),
        (FieldKey.UNIT_TYPE.value, "specialty", Source.STAFF),
        (FieldKey.SALES_CATEGORY.value, "fnb_cafe", Source.STAFF),
        (FieldKey.MALLS.value, ["riyadh-mall-a"], Source.STAFF),
        (FieldKey.FIRST_NAME.value, "Sara", Source.STAFF),
        (FieldKey.LAST_NAME.value, "Ali", Source.STAFF),
        (FieldKey.EMAIL.value, "sara@beanstreet.example", Source.STAFF),
        (FieldKey.MOBILE.value, "+966501234567", Source.STAFF),
    ]
    draft, _, errors = write_fields(draft, entries, master=master)
    assert not errors
    return draft


def _build_cases(runtime: AgentRuntime) -> dict[str, dict]:
    master = load_master_data()
    gate = new_inquiry_draft()
    collecting = new_inquiry_draft()
    collecting.cr_status = "skipped"
    collecting, _, _ = write_fields(
        collecting,
        [
            (FieldKey.COMPANY_NAME.value, "Acme Trading LLC", Source.USER),
            (FieldKey.COMPANY_ADDRESS.value, "King Abdullah Road, Riyadh", Source.USER),
        ],
        master=master,
    )
    verifying = fill_minimal_collectible(new_inquiry_draft(), master)
    verifying.email_verified = False
    verifying.mobile_verified = False
    documents = fill_minimal_collectible(new_inquiry_draft(), master)
    documents.email_verified = True
    documents.mobile_verified = True
    review = _ready_to_submit()
    existing = new_inquiry_draft()
    existing.cr_status = "existing"
    existing, _, _ = write_fields(
        existing,
        [(FieldKey.COMPANY_NAME.value, "Existing Mall Co.", Source.VERIFIED)],
        master=master,
    )
    submitted = _ready_to_submit()
    submitted.reference = "GEO-STR-100001"
    tenant = runtime.services.tenants.get_by_id("T-1002")
    assert tenant is not None
    existing_tenant_draft, _ = prefill_from_tenant(
        new_inquiry_draft(), tenant, master, brand_id=None
    )
    return {
        "phase_gate": _state_for(gate),
        "phase_collecting": _state_for(collecting),
        "phase_verifying": _state_for(verifying),
        "phase_documents": _state_for(documents),
        "phase_review": _state_for(review),
        "phase_existing_account": _state_for(existing),
        "phase_submitted": _state_for(submitted),
        "channel_assisted": _state_for(_assisted_collecting_draft(), assisted=True),
        "channel_existing_tenant": _state_for(
            existing_tenant_draft,
            channel="existing_tenant",
            tenant_id="T-1002",
        ),
    }


@pytest.fixture(autouse=True)
def _fresh_prompt() -> None:
    clear_prompt_cache()
    yield
    clear_prompt_cache()


CASE_IDS = [
    "phase_gate",
    "phase_collecting",
    "phase_verifying",
    "phase_documents",
    "phase_review",
    "phase_existing_account",
    "phase_submitted",
    "channel_assisted",
    "channel_existing_tenant",
]


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_system_prompt_snapshot(case_id: str, agent_runtime: AgentRuntime) -> None:
    cases = _build_cases(agent_runtime)
    rendered = _render(cases[case_id], agent_runtime)
    snapshot_path = _SNAPSHOT_DIR / f"{case_id}.txt"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        _SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(rendered, encoding="utf-8")
        pytest.skip("snapshots updated")
    expected = snapshot_path.read_text(encoding="utf-8")
    if rendered != expected:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                rendered.splitlines(),
                fromfile=f"snapshot/{case_id}.txt",
                tofile="rendered",
                lineterm="",
            )
        )
        lines = diff.splitlines()
        if len(lines) > _MAX_DIFF_LINES:
            extra = len(lines) - _MAX_DIFF_LINES
            diff = "\n".join(lines[:_MAX_DIFF_LINES]) + f"\n… ({extra} more lines)"
        raise AssertionError(f"system prompt changed for {case_id}:\n{diff}")
