"""The sales category as option buttons (18 Nov B1 §3.2, NG2, ADR-N1, ADR-N2).

Options come from master data: category ids are kept, a group id expands to its categories,
unknown ids are dropped, at most `flow_v2_intake.max_choice_options`. Labels follow the
chat's language. The brand name alone never gives options.
"""

from __future__ import annotations

from dataclasses import replace

from app.agent.tools import show_category_options
from app.api.cards import build_choice_card, category_options
from app.domain.master import load_master_data
from app.domain.models import FieldKey
from app.policy.config import get_policy
from langchain_core.messages import HumanMessage
from tests.agent.conftest import make_tool_runtime


def test_group_ids_expand_and_unknown_ids_drop() -> None:
    master = load_master_data()

    assert master.expand_category_candidates(["fnb"], limit=4) == ["fnb_cafe", "fnb_restaurant"]
    assert master.expand_category_candidates(
        ["fashion", "retail", "pharmacy", "fnb_cafe"], limit=4
    ) == ["fashion", "electronics", "fnb_cafe"]
    assert master.expand_category_candidates(["fnb", "retail", "beauty"], limit=4) == [
        "fnb_cafe",
        "fnb_restaurant",
        "fashion",
        "electronics",
    ]
    assert master.expand_category_candidates(["shoes"], limit=4) == []


def test_every_group_names_known_categories() -> None:
    master = load_master_data()
    known = {c.id for c in master.sales_categories}

    assert {g.id for g in master.sales_category_groups} == {
        "fnb",
        "retail",
        "beauty",
        "entertainment",
        "services",
    }
    for group in master.sales_category_groups:
        assert group.categories and set(group.categories) <= known
        assert group.label_ar


def test_the_card_shows_labels_from_data_in_the_chat_language() -> None:
    master = load_master_data()
    options = category_options(master, ["fnb_cafe", "fnb_restaurant"])

    english = build_choice_card("sales_category", options)
    arabic = build_choice_card("sales_category", options, lang="ar")

    assert english.card_id == "choice-sales_category"
    assert english.card_type == "choice"
    assert [o["value"] for o in english.payload["options"]] == ["fnb_cafe", "fnb_restaurant"]
    assert english.payload["options"][0]["label"] == "Food & Beverage · Café"
    assert english.payload["options"][0]["label_ar"] == "أغذية ومشروبات · مقهى"
    assert (english.payload["lang"], english.payload["chosen"]) == ("en", None)
    assert arabic.payload["lang"] == "ar"
    assert arabic.payload["prompt"] != english.payload["prompt"]


def _call(base_state, agent_runtime, stream_events, user_text: str, **args):
    state = {**base_state, "messages": [HumanMessage(content=user_text)]}
    events, writer = stream_events
    runtime = make_tool_runtime(state=state, agent_runtime=agent_runtime, writer=writer)
    result = show_category_options.invoke({"state": state, "runtime": runtime, **args})
    cards = [e["data"] for e in events if e.get("type") == "ui_card"]
    return str(result.update["messages"][0].content), cards


def test_the_tool_shows_options_from_what_they_sell(
    base_state, agent_runtime, stream_events
) -> None:
    text = "we do coffee and breakfast"
    content, cards = _call(
        base_state, agent_runtime, stream_events, text, candidates=["fnb"], evidence=text
    )

    assert content.startswith("Options shown:")
    assert [o["value"] for o in cards[0]["payload"]["options"]] == ["fnb_cafe", "fnb_restaurant"]
    assert base_state["draft"].fields[FieldKey.SALES_CATEGORY].value is None


def test_the_tool_caps_the_options(base_state, agent_runtime, stream_events) -> None:
    text = "food, clothes, gadgets and a salon"
    _content, cards = _call(
        base_state,
        agent_runtime,
        stream_events,
        text,
        candidates=["fnb", "retail", "beauty"],
        evidence=text,
    )

    limit = get_policy().flow_v2_intake.max_choice_options
    assert len(cards[0]["payload"]["options"]) == limit


def test_the_tool_uses_the_chat_language(base_state, agent_runtime, stream_events) -> None:
    text = "نقدم القهوة والفطور"
    _content, cards = _call(
        base_state,
        replace(agent_runtime, lang="ar"),
        stream_events,
        text,
        candidates=["fnb"],
        evidence=text,
    )

    assert cards[0]["payload"]["lang"] == "ar"


def test_no_match_and_brand_only_show_no_card(base_state, agent_runtime, stream_events) -> None:
    unknown, cards = _call(
        base_state,
        agent_runtime,
        stream_events,
        "we sell shoes",
        candidates=["shoes"],
        evidence="we sell shoes",
    )
    assert unknown.startswith("no_category_match")
    assert cards == []

    draft = base_state["draft"]
    draft.fields[FieldKey.BRAND_NAME_EN].value = "Bean Street"
    brand_only, cards = _call(
        {**base_state, "draft": draft},
        agent_runtime,
        stream_events,
        "Bean Street",
        candidates=["fnb_cafe"],
        evidence="Bean Street",
    )
    assert brand_only.startswith("category_needs_what_you_sell")
    assert cards == []
