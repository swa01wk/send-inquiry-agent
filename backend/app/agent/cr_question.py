"""CR numbers in the public chat, and which intake a new chat runs (flow v2 §3.2).

On the public page the Company Registration card takes the CR (Verify) or Skip. A CR number
typed in the chat is removed before it reaches the transcript, the audit trail or the model
(`scrub_cr_numbers`), and checked like the card's Verify. The demo-feedback CR question
("Do you have a CR?", `public_cr_check: ask_then_sign_in`) was removed with flow v2: it isn't
on the chart.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.validation import normalise_digits
from app.policy.config import get_policy

SELF_SERVICE = "self_service"
CR_REMOVED = "[CR number removed]"
CR_NUMBER_IN_REPLY = (
    "[guard] cr_number_in_reply: your reply contained a CR number. Remove it and reply again "
    "without any CR number — point to Sign in if they have a CR, and never repeat or look up "
    "a number."
)

# A CR number: ten digits on their own, not starting with 0 (Saudi local phone numbers do),
# and not part of a longer number (an international phone number, an IBAN). Arabic-Indic
# and Eastern Arabic digits are normalised first. A ten-digit National ID typed in the chat
# matches too; it isn't needed in chat (the documents card takes it), so that's accepted.
_CR_RE = re.compile(r"(?<![\d+])[1-9]\d{9}(?!\d)")


# Scripted e2e scenarios that run the flow v2 public intake (day F3), whatever the policy:
# `flow-v2-s01` … `flow-v2-s17` (S18–S24 start after submit).
FLOW_V2_INTAKE_SCRIPT_PREFIX = "flow-v2-s"
# The demo script's intake (docs/demo-script.md beat 1, `demo` in docs/flow-v2/scenarios.json).
FLOW_V2_DEMO_SCRIPT = "flow-v2-demo"
_FLOW_V2_AFTER_SUBMIT = frozenset(f"flow-v2-s{n}" for n in range(18, 25))
# The 18 Nov demo stories `flow-v2-nv01` … (docs/specs/demo-18nov-feedback.md §5) run the
# flow v2 intake too.
FLOW_V2_NOV18_SCRIPT_PREFIX = "flow-v2-nv"
# Scenario-query variants with their own intake script (e2e/tests/scenario-queries).
QA_FLOW_V2_INTAKE_SCRIPTS = frozenset({"qa-s4-continue"})


def flow_v2_intake_for(session: Any) -> bool:
    """A new self-service inquiry runs the flow v2 intake: the policy switch, or a scripted
    `flow-v2-s…` intake scenario. Staff and tenant-portal channels keep the v1 intake."""
    if session.assisted or (session.channel or SELF_SERVICE) != SELF_SERVICE:
        return False
    scenario = session.test_scenario
    if scenario:
        if scenario == FLOW_V2_DEMO_SCRIPT or scenario in QA_FLOW_V2_INTAKE_SCRIPTS:
            return True
        if scenario.startswith(FLOW_V2_NOV18_SCRIPT_PREFIX):
            return True
        return scenario.startswith(FLOW_V2_INTAKE_SCRIPT_PREFIX) and (
            scenario not in _FLOW_V2_AFTER_SUBMIT
        )
    return get_policy().flow_v2_intake.enabled


def scrub_cr_numbers(text: str) -> tuple[str, bool]:
    """Replace CR-format numbers with a placeholder. Returns (text, found)."""
    # Digit normalisation maps one character to one, so spans found in the normalised text
    # line up with the original, which is kept as typed apart from the removed numbers.
    spans = [m.span() for m in _CR_RE.finditer(normalise_digits(text))]
    if not spans:
        return text, False
    out: list[str] = []
    last = 0
    for start, end in spans:
        out.append(text[last:start])
        out.append(CR_REMOVED)
        last = end
    out.append(text[last:])
    return "".join(out), True


def first_cr_number(text: str) -> str | None:
    """The first CR-format number in the text, digits normalised (flow v2 §3.2)."""
    match = _CR_RE.search(normalise_digits(text))
    return match.group(0) if match else None


def contains_cr_number(text: str) -> bool:
    return bool(_CR_RE.search(normalise_digits(text)))
