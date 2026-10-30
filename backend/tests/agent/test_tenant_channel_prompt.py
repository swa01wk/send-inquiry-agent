"""Channel prompt blocks and tenant brand pick before the agent turn."""

from __future__ import annotations

from unittest.mock import patch

from app.agent.guard import GUARD_PREFIX, guard_node
from app.agent.prompts import tenant_account_notes
from app.agent.runtime import AgentRuntime
from app.agent.state import initial_agent_state
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.domain.rules import compute_phase
from app.domain.tenant_prefill import apply_tenant_brand_pick_from_message, prefill_from_tenant
from langchain_core.messages import AIMessage, HumanMessage


def test_tenant_account_notes_lists_both_t1002_brands(agent_runtime: AgentRuntime) -> None:
    tenant = agent_runtime.services.tenants.get_by_id("T-1002")
    assert tenant is not None
    notes = tenant_account_notes(tenant)
    assert "Noor Fashion (نور للأزياء)" in notes
    assert "Noor Beauty (نور للتجميل)" in notes
    assert "don't ask about mall" in notes


def test_apply_tenant_brand_fills_ar_and_category_when_en_from_user(
    agent_runtime: AgentRuntime,
) -> None:
    tenant = agent_runtime.services.tenants.get_by_id("T-1002")
    assert tenant is not None
    master = load_master_data()
    draft, _ = prefill_from_tenant(new_inquiry_draft(), tenant, master, brand_id=None)
    draft, _, _ = write_fields(
        draft,
        [(FieldKey.BRAND_NAME_EN.value, "Noor Beauty", Source.USER)],
        master=master,
    )
    updated, written = apply_tenant_brand_pick_from_message(
        draft,
        tenant,
        master,
        "It's for Noor Beauty.",
    )
    assert FieldKey.BRAND_NAME_AR.value in written
    assert FieldKey.SALES_CATEGORY.value in written
    assert updated.fields[FieldKey.BRAND_NAME_AR].value == "نور للتجميل"
    assert updated.fields[FieldKey.SALES_CATEGORY].value == "beauty"
    assert updated.fields[FieldKey.BRAND_NAME_EN].source == Source.VERIFIED


def test_assisted_guard_requires_show_application_link_when_basic_info_complete(
    agent_runtime: AgentRuntime,
) -> None:
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
    draft, _, _ = write_fields(draft, entries, master=master)
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-assisted-guard", draft=draft, phase=phase)
    state["assisted"] = True
    state["messages"] = [
        HumanMessage(content="Sara Ali, sara@beanstreet.example, 0501234567"),
        AIMessage(content="Thanks — I'll send a verification link to Sara's email."),
    ]
    with patch("app.agent.guard.get_stream_writer", return_value=None):
        result = guard_node(state, runtime=agent_runtime)
    assert result.get("retry_agent") is True
    note = result["messages"][0].content
    assert isinstance(note, str)
    assert GUARD_PREFIX in note
    assert "show_application_link" in note


def test_assisted_guard_verification_send_claim_when_basic_info_incomplete(
    agent_runtime: AgentRuntime,
) -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-assisted-verify-claim", draft=draft, phase=phase)
    state["assisted"] = True
    state["messages"] = [
        HumanMessage(content="Hi, I'm calling about a kiosk."),
        AIMessage(content="I've sent the verification link to your email."),
    ]
    with patch("app.agent.guard.get_stream_writer", return_value=None):
        result = guard_node(state, runtime=agent_runtime)
    assert result.get("retry_agent") is True
    note = result["messages"][0].content
    assert isinstance(note, str)
    assert "Assisted mode: don't send or promise a verification link or code" in note
    assert "show_application_link" not in note


def test_assisted_guard_no_note_when_caller_verifies_from_link(
    agent_runtime: AgentRuntime,
) -> None:
    draft = new_inquiry_draft()
    draft.cr_status = "skipped"
    phase = compute_phase(draft).value
    state = initial_agent_state(session_id="sess-assisted-caller-verify", draft=draft, phase=phase)
    state["assisted"] = True
    state["messages"] = [
        HumanMessage(content="Thanks."),
        AIMessage(content="The caller will verify their email from the link."),
    ]
    with patch("app.agent.guard.get_stream_writer", return_value=None):
        result = guard_node(state, runtime=agent_runtime)
    assert result.get("retry_agent") is not True


def _assisted_contact_state(reply: str, agent_runtime: AgentRuntime):  # type: ignore[no-untyped-def]
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(),
        [(FieldKey.FIRST_NAME.value, "Sara", Source.STAFF)],
        master=master,
    )
    draft.cr_status = "skipped"
    state = initial_agent_state(
        session_id="sess-assisted-name", draft=draft, phase=compute_phase(draft).value
    )
    state["assisted"] = True
    state["messages"] = [
        HumanMessage(content="Sara Ali, sara@beanstreet.example, 0501234567."),
        AIMessage(content=reply),
    ]
    with patch("app.agent.guard.get_stream_writer", return_value=None):
        return guard_node(state, runtime=agent_runtime)


def test_assisted_guard_retries_when_reply_thanks_the_caller_by_name(
    agent_runtime: AgentRuntime,
) -> None:
    result = _assisted_contact_state(
        "Thanks, Sara — I've saved the contact details.",
        agent_runtime,
    )
    assert result.get("retry_agent") is True
    note = result["messages"][0].content
    assert isinstance(note, str) and "Don't greet or thank the caller by name" in note


def test_assisted_guard_allows_possessive_name(agent_runtime: AgentRuntime) -> None:
    result = _assisted_contact_state("Thanks — I've saved Sara's details.", agent_runtime)
    note = result["messages"][0].content if result.get("messages") else ""
    assert "Don't greet or thank the caller by name" not in str(note)
