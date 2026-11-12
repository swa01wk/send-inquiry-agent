"""Flow v2 public intake rules outside the API (spec flow-v2-alignment §3.3, §6; day F3):
the v2 policy view, Office routing, the brand-only category check and invariant I9."""

from __future__ import annotations

from app.agent.invariants import TurnContext, check_turn
from app.agent.tools import DraftFieldUpdate, _category_from_brand_only
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import FieldKey, Source
from app.policy.config import get_policy, intake_flow, intake_scope
from app.workflow.service import route_queue
from tests.domain.conftest import fill_minimal_collectible


def test_v2_view_changes_only_the_intake_values() -> None:
    v1 = get_policy()
    with intake_scope("v2"):
        assert intake_flow() == "v2"
        v2 = get_policy()
    assert v2.product_lines == ["store", "office"]
    assert v2.max_malls_per_inquiry == 5
    assert v2.public_cr_check == "verify_or_skip"
    assert v2.review_routing == v1.review_routing
    assert get_policy() is v1


def test_office_routes_to_the_store_reviewer() -> None:
    master = load_master_data()
    draft = fill_minimal_collectible(new_inquiry_draft(), master)
    with intake_scope("v2"):
        draft, _, errors = write_fields(
            draft, [(FieldKey.UNIT_TYPE.value, "office", Source.USER)], master=master
        )
        assert not errors
        queue = route_queue(draft, master)
    assert queue is not None
    assert queue.product_line == "office"
    assert queue.role == "rlm_store"
    assert master.unit_code("office") == "OFF"


def test_office_is_not_offered_on_the_v1_intake() -> None:
    master = load_master_data()
    _draft, _, errors = write_fields(
        new_inquiry_draft(), [(FieldKey.UNIT_TYPE.value, "office", Source.USER)], master=master
    )
    assert FieldKey.UNIT_TYPE.value in errors


def _category(evidence: str | None) -> DraftFieldUpdate:
    return DraftFieldUpdate(
        key=FieldKey.SALES_CATEGORY.value, value="fnb_cafe", source="derived", evidence=evidence
    )


def test_category_from_the_brand_name_alone_is_refused() -> None:
    draft = new_inquiry_draft()
    brand = DraftFieldUpdate(key=FieldKey.BRAND_NAME_EN.value, value="Bean Street", source="user")
    item = _category("Bean Street")
    assert _category_from_brand_only(item, [brand, item], draft)
    assert _category_from_brand_only(_category(None), [], draft)


def test_category_from_what_they_sell_is_kept() -> None:
    draft = new_inquiry_draft()
    brand = DraftFieldUpdate(key=FieldKey.BRAND_NAME_EN.value, value="Bean Street", source="user")
    item = _category("we sell specialty coffee")
    assert not _category_from_brand_only(item, [brand, item], draft)


def test_i9_flags_a_unit_named_before_submit() -> None:
    hits = check_turn(
        TurnContext(assistant_text="Unit SPC-12 in Mall A is free.", flow_v2_intake=True)
    )
    assert "I9" in [h.invariant for h in hits]


def test_i9_allows_asking_for_the_unit_type() -> None:
    text = "Which unit type do you need: store or office?"
    hits = check_turn(TurnContext(assistant_text=text, flow_v2_intake=True))
    assert "I9" not in [h.invariant for h in hits]


def test_i9_is_off_outside_the_v2_intake() -> None:
    hits = check_turn(TurnContext(assistant_text="Unit SPC-12 in Mall A is free."))
    assert "I9" not in [h.invariant for h in hits]
