"""No rule the policy covers is hard-coded in validators, rules, cards, tools or the prompt.

L3 §3.7 acceptance ("prompt-only policy" anti-pattern): if one of these patterns comes
back, the code or the prompt can drift from app/policy/policy.yaml.
"""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
PROMPT_FILES = [
    APP / "agent" / "system_prompt.md",
    Path(__file__).resolve().parents[3] / "docs" / "agent-system-prompt.md",
]

CODE_PATTERNS: list[tuple[str, str]] = [
    ("domain/validation.py", r"len\(set\(raw\)\)\s*>\s*1\b"),
    ("domain/fields.py", r"DOCUMENT_DEFINITIONS"),
    ("domain/fields.py", r"\(DocType\.\w+,\s*\"[^\"]+\",\s*(True|False)\)"),
    ("domain/rules.py", r"DOCUMENT_DEFINITIONS"),
    ("domain/summary.py", r"DOCUMENT_DEFINITIONS"),
    ("agent/actions.py", r"DOCUMENT_DEFINITIONS"),
    ("agent/mall_match.py", r"len\(ids\)\s*!=\s*1"),
    ("agent/tools.py", r"len\(accepted\)\s*>\s*1\b"),
    ("api/cards.py", r"max_select=1\b"),
]

# Rule statements that now live in the "Rules in force" block, not in the static prompt.
PROMPT_PATTERNS: list[str] = [
    r"an inquiry is for \*\*one mall\*\*",
    r"\*\*Company Profile\*\* and \*\*Brand Profile\*\* are required",
    r"a landline-only applicant is verified by the email link alone",
    r"verification card: email link, plus SMS code",
    r"If the account already exists, explain kindly",
]


@pytest.mark.parametrize(("relative", "pattern"), CODE_PATTERNS)
def test_code_reads_the_policy(relative: str, pattern: str) -> None:
    text = (APP / relative).read_text(encoding="utf-8")
    assert not re.search(pattern, text), f"{relative} hard-codes a policy rule: {pattern}"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: p.name)
@pytest.mark.parametrize("pattern", PROMPT_PATTERNS)
def test_prompt_leaves_rules_to_the_block(path: Path, pattern: str) -> None:
    text = path.read_text(encoding="utf-8")
    static = text.split("## Rules in force (rendered")[0]  # docs copy shows the block below
    assert not re.search(pattern, static), f"{path.name} states a policy rule: {pattern}"
