"""Parity scenario scripts: user actions + scripted model steps."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from tests.scenarios import agent_steps as catalogue

ScriptKind = Literal[
    "message",
    "confirm_latest",
    "action",
    "upload",
    "verify_email",
    "submit_otp",
]


@dataclass
class ScriptStep:
    kind: ScriptKind
    text: str | None = None
    action: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    doc_type: str | None = None
    file_name: str | None = None
    content: bytes = b"%PDF-1.4 minimal"


@dataclass
class ParityScenario:
    name: str
    model_steps: list[dict[str, Any]]
    script: list[ScriptStep]


_AFTER_VERIFICATION_STEPS: list[dict[str, Any]] = [
    {
        "content": "",
        "tool_calls": [
            {
                "name": "request_documents",
                "args": {},
                "id": "parity-docs",
                "type": "tool_call",
            }
        ],
    },
    {"content": "Company Profile and Brand Profile are required. Optional documents can follow."},
    {
        "content": "",
        "tool_calls": [
            {
                "name": "show_review",
                "args": {},
                "id": "parity-review",
                "type": "tool_call",
            }
        ],
    },
    {"content": "Please review everything on the card when you're ready."},
]

_DOC_UPLOAD_SCRIPT: list[ScriptStep] = [
    ScriptStep(
        kind="upload",
        doc_type="company_profile",
        file_name="company_profile.pdf",
    ),
    ScriptStep(
        kind="upload",
        doc_type="brand_profile",
        file_name="brand_profile.pdf",
    ),
    ScriptStep(kind="action", action="documents_updated"),
]

_HAPPY_PATH_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="My CR number is 1010123456"),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(
        kind="message",
        text=(
            "Bean Street specialty coffee kiosk at Riyadh Mall A — Sara Ali, "
            "sara@beanstreet.example, +966501234567"
        ),
    ),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(kind="verify_email"),
    ScriptStep(kind="submit_otp", payload={"code": "1234"}),
    *_DOC_UPLOAD_SCRIPT,
]

_SKIP_CR_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="I don't have my CR with me — can we skip it?"),
    ScriptStep(
        kind="message",
        text=(
            "Acme Trading LLC on King Abdullah Road. We run a café kiosk called Bean Street "
            "at Riyadh Mall A. Contact Sara Ali at sara@beanstreet.example / +966501234567."
        ),
    ),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(kind="verify_email"),
    ScriptStep(kind="submit_otp", payload={"code": "1234"}),
    *_DOC_UPLOAD_SCRIPT,
]

_LANDLINE_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="I don't have my CR with me — can we skip it?"),
    ScriptStep(
        kind="message",
        text=(
            "Acme Trading LLC, King Abdullah Road, Riyadh. Bean Street café kiosk at "
            "Riyadh Mall A. Sara Ali, sara@beanstreet.example, office landline 011234567."
        ),
    ),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(kind="verify_email"),
    *_DOC_UPLOAD_SCRIPT,
]

_TWO_MALLS_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="I don't have my CR with me — can we skip it?"),
    ScriptStep(
        kind="message",
        text=(
            "Acme Trading LLC, King Abdullah Road. Bean Street café kiosks at Riyadh Mall A "
            "and Mall of Arabia."
        ),
    ),
]

_WRONG_OTP_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="My CR number is 1010123456"),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(
        kind="message",
        text="Bean Street kiosk riyadh mall a Sara Ali sara@beanstreet.example 0501234567",
    ),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(kind="verify_email"),
    ScriptStep(kind="action", action="submit_otp", payload={"code": "0000"}),
    ScriptStep(kind="action", action="submit_otp", payload={"code": "0000"}),
    ScriptStep(kind="action", action="submit_otp", payload={"code": "0000"}),
    ScriptStep(kind="action", action="submit_otp", payload={"code": "1234"}),
    *_DOC_UPLOAD_SCRIPT,
]

_S14_USER: list[ScriptStep] = [
    ScriptStep(kind="message", text="1010123456"),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(
        kind="message",
        text="Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567",
    ),
    ScriptStep(kind="confirm_latest"),
    ScriptStep(kind="action", action="submit_otp", payload={"code": "1234"}),
    *_DOC_UPLOAD_SCRIPT,
    ScriptStep(kind="verify_email"),
]


def _load_e2e_steps(name: str) -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "e2e_scripts" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def all_scenarios() -> list[ParityScenario]:
    wrong_otp_steps = catalogue.model_steps_for("12-wrong-code") + [
        {"content": "Sorry — that didn't match. A fresh SMS code was sent; try again in the box."},
        *_AFTER_VERIFICATION_STEPS,
    ]
    return [
        ParityScenario(
            name="happy-path-cr",
            model_steps=catalogue.HAPPY_PATH_CR_STEPS + _AFTER_VERIFICATION_STEPS,
            script=_HAPPY_PATH_USER,
        ),
        ParityScenario(
            name="skip-cr",
            model_steps=catalogue.SKIP_CR_STEPS + _AFTER_VERIFICATION_STEPS,
            script=_SKIP_CR_USER,
        ),
        ParityScenario(
            name="existing-cr-sign-in",
            model_steps=catalogue.EXISTING_CR_STEPS,
            script=[ScriptStep(kind="message", text="1010000000")],
        ),
        ParityScenario(
            name="landline-only",
            model_steps=catalogue.LANDLINE_ONLY_STEPS + _AFTER_VERIFICATION_STEPS,
            script=_LANDLINE_USER,
        ),
        ParityScenario(
            name="two-malls-named",
            model_steps=catalogue.TWO_MALLS_NAMED_STEPS,
            script=_TWO_MALLS_USER,
        ),
        ParityScenario(
            name="wrong-otp-three-times",
            model_steps=wrong_otp_steps,
            script=_WRONG_OTP_USER,
        ),
        ParityScenario(
            name="s14-out-of-order",
            model_steps=_load_e2e_steps("s14-out-of-order"),
            script=_S14_USER,
        ),
    ]


def scenario_by_name(name: str) -> ParityScenario:
    for scenario in all_scenarios():
        if scenario.name == name:
            return scenario
    msg = f"unknown parity scenario: {name}"
    raise KeyError(msg)
