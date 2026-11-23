"""The four product lines on the public intake (18 Nov B1, N1, M34, NG1) and the policy
values B1 adds: example answers in Rules in force, the option cap, and the switch that keeps
the sales category to the option buttons."""

from __future__ import annotations

import pytest
from app.agent.prompts import rules_in_force
from app.agent.tools import update_draft
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.policy.config import get_policy, intake_scope
from app.workflow.service import route_queue
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime
from tests.domain.conftest import fill_minimal_collectible


def test_the_public_intake_offers_all_four_product_lines() -> None:
    with intake_scope("v2"):
        policy = get_policy()
    assert policy.product_lines == ["store", "office", "media", "specialty"]
    assert set(policy.product_lines) <= set(policy.review_routing)


@pytest.mark.parametrize(
    ("unit_type", "code", "final_role"),
    [
        ("media", "MED", "rplm_media"),
        ("specialty", "SPC", "rplm_specialty"),
        ("store", "STR", "rlm_store"),
        ("office", "OFF", "rlm_store"),
    ],
)
def test_each_line_gets_its_reference_code_and_final_reviewer(
    unit_type: str, code: str, final_role: str
) -> None:
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    with intake_scope("v2"):
        draft, _, errors = write_fields(
            draft, [(FieldKey.UNIT_TYPE.value, unit_type, Source.USER)], master=master
        )
        assert not errors
        queue = route_queue(draft, master)
    assert master.unit_code(unit_type) == code
    # The Leasing Admin acts first on every line; the case sets that (first_level_review_role).
    assert queue is not None
    assert queue.role_for("final") == final_role


def test_rules_in_force_quote_the_policy_examples() -> None:
    master = load_master_data()
    with intake_scope("v2"):
        policy = get_policy()
        text = rules_in_force(policy, master)
    examples = policy.flow_v2_intake.examples
    for example in (examples.what_you_sell, examples.office_business, examples.basic_info_answer):
        assert example in text
    assert "Media" in text and "Specialty" in text


def test_the_option_cap_is_policy() -> None:
    assert get_policy().flow_v2_intake.max_choice_options == 4


def test_category_from_options_only_refuses_update_draft(
    base_state, agent_runtime, stream_events, monkeypatch
) -> None:
    policy = get_policy()
    strict = policy.model_copy(
        update={
            "flow_v2_intake": policy.flow_v2_intake.model_copy(
                update={"category_from_options_only": True}
            )
        }
    )
    draft = new_inquiry_draft()
    draft.intake_flow = "v2"
    state = {
        **base_state,
        "draft": draft,
        "messages": [HumanMessage(content="we sell coffee")],
    }
    _events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    fields = [
        {"key": "sales_category", "value": "fnb_cafe", "source": "derived", "evidence": "coffee"}
    ]

    import app.agent.tools as tools

    monkeypatch.setattr(tools, "get_policy", lambda: strict)
    result = update_draft.invoke({"state": state, "runtime": runtime, "fields": fields})

    assert "use_show_category_options" in str(result.update["messages"][0].content)
    assert result.update["draft"].fields[FieldKey.SALES_CATEGORY].value is None


def test_the_basic_info_example_names_no_registry_company() -> None:
    # Invariant I8: the public chat never shows company details from a CR lookup, so the
    # example answer can't use one (live eval 24 Nov: "King Fahd Road, Riyadh").
    from app.agent.invariants import _registry_details

    example = get_policy().flow_v2_intake.examples.basic_info_answer.lower()
    assert not [detail for detail in _registry_details() if detail in example]


def test_update_draft_after_a_tap_says_it_is_already_set(
    base_state, agent_runtime, stream_events, monkeypatch
) -> None:
    policy = get_policy()
    strict = policy.model_copy(
        update={
            "flow_v2_intake": policy.flow_v2_intake.model_copy(
                update={"category_from_options_only": True}
            )
        }
    )
    master = load_master_data()
    draft, _, _ = write_fields(
        new_inquiry_draft(), [("sales_category", "fnb_cafe", Source.USER)], master=master
    )
    draft.intake_flow = "v2"
    state = {**base_state, "draft": draft, "messages": [HumanMessage(content="ok")]}
    _events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    import app.agent.tools as tools

    monkeypatch.setattr(tools, "get_policy", lambda: strict)
    fields = [{"key": "sales_category", "value": "fnb_cafe", "source": "user"}]
    result = update_draft.invoke({"state": state, "runtime": runtime, "fields": fields})

    assert "already_set_by_the_users_tap" in str(result.update["messages"][0].content)
