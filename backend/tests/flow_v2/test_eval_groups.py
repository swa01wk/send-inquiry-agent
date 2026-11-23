"""`GROUP` selection in `scripts/eval_live.py` (demo-18nov spec §6).

`nov18` runs every 18 Nov demo group; the groups e2e.yml offers before their scenarios land
are known, so an empty run of one of them is not a typo.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import eval_live  # noqa: E402


def _scenario(name: str, group: str) -> eval_live.LiveScenario:
    return eval_live.LiveScenario(
        name=name, user_turns=["hi"], evaluate=lambda _turns: [], group=group
    )


def test_nov18_selects_every_demo_group_and_nothing_else() -> None:
    scenarios = [_scenario(f"s-{g}", g) for g in sorted(eval_live.NOV18_GROUPS)]
    scenarios += [_scenario("old", "flow_v2"), _scenario("case", "case")]
    picked = eval_live.select_group(scenarios, "nov18")
    assert {s.group for s in picked} == eval_live.NOV18_GROUPS
    assert len(picked) == len(eval_live.NOV18_GROUPS)


def test_a_single_group_selects_only_itself() -> None:
    scenarios = [_scenario("a", "mall_fuzzy"), _scenario("b", "property_sequence")]
    assert [s.name for s in eval_live.select_group(scenarios, "mall_fuzzy")] == ["a"]


def test_planned_groups_match_the_dispatch_options() -> None:
    workflow = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "e2e.yml"
    text = workflow.read_text(encoding="utf-8")
    for group in eval_live.PLANNED_GROUPS:
        assert group in text, f"e2e.yml doesn't offer GROUP={group}"
