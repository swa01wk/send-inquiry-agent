"""Flip each policy value and the behaviour changes, with no code or prompt edits (L3 §3.7)."""

from app.agent.mall_match import fill_mentioned_malls
from app.agent.prompts import build_system_message, rules_in_force
from app.agent.tools import get_master_data, verify_cr
from app.api.cards import build_mall_picker_card
from app.domain import validation as v
from app.domain.draft_ops import new_inquiry_draft, write_fields
from app.domain.master import load_master_data
from app.domain.models import DocType, FieldKey, Source
from app.domain.rules import can_submit
from app.domain.summary import build_draft_summary
from app.policy.config import load_policy, use_policy
from tests.agent.conftest import make_tool_runtime
from tests.domain.conftest import fill_minimal_collectible

TWO_MALLS = ["riyadh-mall-a", "riyadh-mall-b"]


def _policy(**changes):
    return load_policy().with_changes(**changes)


# ---- max_malls_per_inquiry ------------------------------------------------------------


def test_default_policy_allows_one_mall() -> None:
    result = v.validate_malls(TWO_MALLS, load_master_data())
    assert isinstance(result, v.ValidationError)
    assert result.code == "one_mall_per_inquiry"


def test_max_malls_two_accepts_two_malls() -> None:
    master = load_master_data()
    with use_policy(_policy(max_malls_per_inquiry=2)):
        assert v.validate_malls(TWO_MALLS, master) == TWO_MALLS
        too_many = v.validate_malls([*TWO_MALLS, "riyadh-mall-c"], master)
        assert isinstance(too_many, v.ValidationError)
        assert too_many.code == "too_many_malls"
        card = build_mall_picker_card(new_inquiry_draft(), master, "riyadh")
        assert card.payload["max_select"] == 2
        draft, filled = fill_mentioned_malls(
            new_inquiry_draft(), "Riyadh Mall A or Riyadh Mall B", master
        )
        assert filled
        assert draft.fields[FieldKey.MALLS].value == TWO_MALLS


def test_default_mall_picker_selects_one() -> None:
    card = build_mall_picker_card(new_inquiry_draft(), load_master_data(), "riyadh")
    assert card.payload["max_select"] == 1


# ---- existing_tenant_policy -------------------------------------------------------------


def _verify_existing_cr(agent_runtime, base_state, stream_events):
    _events, writer = stream_events
    runtime = make_tool_runtime(state=base_state, agent_runtime=agent_runtime, writer=writer)
    return verify_cr.invoke({"cr_number": "1010000000", "state": base_state, "runtime": runtime})


def test_sign_in_policy_stops_an_existing_cr(agent_runtime, base_state, stream_events) -> None:
    result = _verify_existing_cr(agent_runtime, base_state, stream_events)
    draft = result.update["draft"]
    assert draft.cr_status == "existing"
    assert [b.token for b in can_submit(draft)][0] == "cr_existing"


def test_allow_inquiry_lets_an_existing_cr_continue(
    agent_runtime, base_state, stream_events
) -> None:
    with use_policy(_policy(existing_tenant_policy="allow_inquiry")):
        result = _verify_existing_cr(agent_runtime, base_state, stream_events)
    draft = result.update["draft"]
    assert draft.cr_status == "new"
    assert draft.fields[FieldKey.CR_NUMBER].value == "1010000000"
    assert "cr_existing" not in [b.token for b in can_submit(draft)]
    assert "existing Tenant Central account" in result.update["messages"][0].content


# ---- phone.allowed_countries --------------------------------------------------------------


def test_any_country_accepts_a_uk_number() -> None:
    assert v.normalise_mobile("+447700900123") == "+447700900123"


def test_country_list_rejects_other_countries() -> None:
    with use_policy(_policy(phone={"allowed_countries": ["971"]})):
        assert v.normalise_mobile("+971501234567") == "+971501234567"
        rejected = v.normalise_mobile("+447700900123")
        assert isinstance(rejected, v.ValidationError)
        assert rejected.code == "phone_country_not_allowed"
        classified = v.classify_contact_number("+447700900123")
        assert isinstance(classified, v.ValidationError)
        # Saudi numbers are always accepted.
        assert v.normalise_mobile("0501234567") == "+966501234567"


# ---- documents ------------------------------------------------------------------------------


def _ready_except_documents():
    draft = fill_minimal_collectible(new_inquiry_draft(), load_master_data())
    draft.email_verified = True
    draft.mobile_verified = True
    return draft


def test_default_policy_requires_brand_profile() -> None:
    tokens = [b.token for b in can_submit(_ready_except_documents())]
    assert "missing_document:brand_profile" in tokens


def test_removing_a_required_document_clears_its_blocker() -> None:
    optional_brand = {
        "required": ["company_profile"],
        "optional": [
            "brand_profile",
            "cr_certificate",
            "vat_certificate",
            "national_id",
            "national_address",
            "articles_of_association",
        ],
    }
    with use_policy(_policy(documents=optional_brand)):
        draft = _ready_except_documents()
        tokens = [b.token for b in can_submit(draft)]
        assert "missing_document:brand_profile" not in tokens
        assert "missing_document:company_profile" in tokens
        summary = build_draft_summary(draft, load_master_data())
        assert summary.checks.required_docs_total == 1
        brand_row = next(d for d in summary.documents if d.doc_type == DocType.BRAND_PROFILE)
        assert brand_row.required is False


# ---- product_lines --------------------------------------------------------------------------


def test_removing_a_product_line_rejects_that_unit_type(agent_runtime) -> None:
    master = load_master_data()
    _draft, written, errors = write_fields(
        new_inquiry_draft(), [("unit_type", "media", Source.USER)], master=master
    )
    assert "unit_type" in written
    with use_policy(_policy(product_lines=["store", "specialty"])):
        _draft, written, errors = write_fields(
            new_inquiry_draft(), [("unit_type", "media", Source.USER)], master=master
        )
        assert "unit_type" in errors
        listed = get_master_data.invoke(
            {
                "kind": "unit_types",
                "runtime": make_tool_runtime(
                    state={"session_id": "s"}, agent_runtime=agent_runtime, writer=lambda _: None
                ),
            }
        )
        assert '"media"' not in listed


# ---- Rules in force ---------------------------------------------------------------------------


def test_rules_in_force_follow_the_policy() -> None:
    master = load_master_data()
    default = rules_in_force(load_policy(), master)
    assert "one mall per inquiry" in default
    assert "Documents required to submit: Company Profile, Brand Profile." in default
    assert "point them to Sign In" in default
    assert "any other country" in default

    flipped = rules_in_force(
        _policy(
            max_malls_per_inquiry=2,
            existing_tenant_policy="allow_inquiry",
            phone={"allowed_countries": ["971", "973"]},
        ),
        master,
    )
    assert "up to 2 malls per inquiry" in flipped
    assert "+971, +973" in flipped
    assert "they may continue this inquiry here" in flipped


def test_system_message_carries_the_rules_block() -> None:
    message = build_system_message(new_inquiry_draft(), load_master_data())
    content = str(message.content)
    assert "## Rules in force" in content
    assert content.index("## Rules in force") < content.index("## Current state")
