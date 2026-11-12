"""Turn flow-v2 scenario steps into scripted model JSON (day F3)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "docs" / "flow-v2" / "scenarios.json"


def _load_catalogue() -> list[dict[str, Any]]:
    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    assert isinstance(scenarios, list)
    return scenarios


def _agent_turns_after_cr_registered() -> list[dict[str, Any]]:
    return [
        {
            "content": (
                "You're already registered with us — please sign in to Tenant Central "
                "using the button below."
            )
        },
        {
            "content": (
                "Signing in is still the quickest way — your company details are already "
                "on file there."
            )
        },
    ]


def _agent_turns_after_cr_skipped() -> list[dict[str, Any]]:
    return [
        {
            "content": "",
            "tool_calls": [
                {
                    "name": "suggest_replies",
                    "args": {"options": ["Store", "Office"]},
                    "id": "fv2-unit-offer",
                    "type": "tool_call",
                }
            ],
        },
        {"content": "Got it — a store. What do you sell? That helps us pick the right category."},
    ]


def _step_to_turns(step: dict[str, Any], *, after_cr: str | None) -> list[dict[str, Any]]:
    if "say" in step:
        text = step["say"]
        if re.search(r"\bstore\b", text, re.I):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {
                                "fields": [
                                    {"key": "unit_type", "value": "store", "source": "user"},
                                ]
                            },
                            "id": "fv2-ut",
                            "type": "tool_call",
                        }
                    ],
                },
                {"content": "What do you sell? I'll map it to the right sales category."},
            ]
        if re.search(r"sell|coffee|office", text, re.I):
            fields: list[dict[str, Any]] = [
                {
                    "key": "sales_category",
                    "value": "fnb_cafe" if "coffee" in text.lower() else "fashion",
                    "source": "derived",
                    "evidence": text[:80],
                }
            ]
            if re.search(r"\boffice\b", text, re.I):
                fields = [{"key": "unit_type", "value": "office", "source": "user"}]
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {"fields": fields},
                            "id": "fv2-cat",
                            "type": "tool_call",
                        }
                    ],
                },
                {"content": "Check the summary card and let me know if anything's off."},
            ]
        if "@" in text or re.search(r"\d{9,}", text):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {"fields": _contact_fields_from_say(text)},
                            "id": "fv2-contact",
                            "type": "tool_call",
                        },
                        {
                            "name": "send_verification",
                            "args": {},
                            "id": "fv2-v",
                            "type": "tool_call",
                        },
                    ],
                },
                {
                    "content": (
                        "Thanks — I've sent the verification link and SMS code on the card below."
                    )
                },
            ]
        if re.search(r"mall|sqm|year", text, re.I):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {"fields": _property_fields_from_say(text)},
                            "id": "fv2-prop",
                            "type": "tool_call",
                        }
                    ],
                },
                {
                    "content": (
                        "Your property details are on the card — confirm them when you're ready."
                    )
                },
            ]
        return [{"content": "Thanks — let's keep going with the next step."}]
    if "confirm_card" in step:
        return [{"content": "Looks good — here's what's next in the flow."}]
    if step.get("accept_terms"):
        return [
            {
                "content": (
                    "Thanks — upload the Company Profile and Brand Profile on the card below."
                )
            }
        ]
    if after_cr == "registered":
        return _agent_turns_after_cr_registered()
    if after_cr == "skipped":
        return _agent_turns_after_cr_skipped()
    return []


def _contact_fields_from_say(text: str) -> list[dict[str, Any]]:
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    mobile = re.search(r"0?5\d{8}", text.replace(" ", ""))
    names = text.split(",")[0].strip().split()
    first = names[0] if names else "Sara"
    last = names[1] if len(names) > 1 else "Ali"
    fields = [
        {"key": "first_name", "value": first, "source": "user"},
        {"key": "last_name", "value": last, "source": "user"},
        {
            "key": "email",
            "value": email.group(0) if email else "sara@beanstreet.example",
            "source": "user",
        },
    ]
    if mobile:
        fields.append({"key": "contact_number", "value": mobile.group(0), "source": "user"})
    for key in ("company_name", "company_address", "brand_name_en", "brand_name_ar"):
        if key.replace("_", " ") in text.lower() or "bean" in text.lower():
            pass
    chunk = text
    if "Trading" in text:
        fields.extend(
            [
                {"key": "company_name", "value": "Bean Street Trading Co.", "source": "user"},
                {
                    "key": "company_address",
                    "value": "King Fahd Road Al Olaya Riyadh",
                    "source": "user",
                },
                {"key": "brand_name_en", "value": "Bean Street", "source": "user"},
                {"key": "brand_name_ar", "value": "بين ستريت", "source": "user"},
            ]
        )
    elif len(chunk) > 40:
        fields.append({"key": "company_name", "value": "Acme Trading LLC", "source": "user"})
    return fields


def _property_fields_from_say(text: str) -> list[dict[str, Any]]:
    malls = []
    if "Riyadh Mall A" in text:
        malls.append("riyadh-mall-a")
    if "Mall of Arabia" in text or "mall b" in text.lower():
        malls.append("riyadh-mall-b")
    fields: list[dict[str, Any]] = []
    if malls:
        fields.append({"key": "malls", "value": malls, "source": "user"})
    if "sqm" in text.lower():
        fields.extend(
            [
                {"key": "area_min", "value": 30, "source": "user"},
                {"key": "area_max", "value": 50, "source": "user"},
            ]
        )
    if "250" in text or "180" in text:
        fields.append({"key": "rent_max", "value": 250000, "source": "user"})
    if "3 year" in text.lower():
        fields.append({"key": "lease_period", "value": "3y", "source": "user"})
    return fields


def compile_scenario(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    after_cr: str | None = None
    for step in scenario.get("steps", []):
        if step.get("cr_skip_confirm"):
            after_cr = "skipped"
            steps.extend(_agent_turns_after_cr_skipped())
            continue
        if "cr_verify" in step:
            after_cr = "registered"
            steps.extend(_agent_turns_after_cr_registered())
            continue
        if step.get("cr_skip"):
            continue
        if (
            step.get("verify_email")
            or step.get("enter_code")
            or step.get("upload")
            or step.get("submit")
        ):
            continue
        steps.extend(_step_to_turns(step, after_cr=after_cr))
    if not steps:
        steps = [{"content": "Thanks — let's continue with your inquiry."}]
    return steps


def write_intake_scripts(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for scenario in _load_catalogue():
        sid = scenario.get("id", "")
        if not re.fullmatch(r"S([1-9]|1[0-7])", sid or ""):
            continue
        name = f"flow-v2-{sid.lower()}"
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(compile_scenario(scenario), indent=2) + "\n", encoding="utf-8")
        written += 1
    return written


if __name__ == "__main__":
    n = write_intake_scripts(ROOT / "backend" / "tests" / "e2e_scripts")
    print(f"Wrote {n} flow-v2 intake scripts")
